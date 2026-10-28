// Label a stripped IL2CPP dylib from our own tables, give every listed
// function the body its method table implies, type each class's static-field
// block, then decompile the targets. Args: labels.tsv statics.tsv methods.tsv
// targets.txt outdir.
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.data.CategoryPath;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DataTypeConflictHandler;
import ghidra.program.model.data.DataTypeManager;
import ghidra.program.model.data.IntegerDataType;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.data.QWordDataType;
import ghidra.program.model.data.StructureDataType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.app.script.GhidraScript;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public class DecompileTyped extends GhidraScript {
  private AddressSpace space;
  private long[] starts;

  private Address at(long offset) {
    return space.getAddress(offset);
  }

  private Function functionWithBody(Address entry) throws Exception {
    long start = entry.getOffset();
    int i = java.util.Arrays.binarySearch(starts, start);
    long end = (i >= 0 && i + 1 < starts.length) ? starts[i + 1] - 1 : -1;
    disassemble(entry);
    Function function = getFunctionAt(entry);
    if (end > start) {
      AddressSet body = new AddressSet(entry, at(end));
      if (function == null) {
        new CreateFunctionCmd(null, entry, body, SourceType.IMPORTED).applyTo(currentProgram);
        function = getFunctionAt(entry);
      } else {
        function.setBody(body);
      }
    }
    if (function == null) {
      function = createFunction(entry, null);
    }
    return function;
  }

  @Override
  public void run() throws Exception {
    String[] args = getScriptArgs();
    space = currentProgram.getAddressFactory().getDefaultAddressSpace();
    SymbolTable symbols = currentProgram.getSymbolTable();
    int made = 0;
    for (String line : Files.readAllLines(Paths.get(args[0]))) {
      String[] parts = line.split("\t", 2);
      Address a = at(Long.decode(parts[0]));
      if (!currentProgram.getMemory().contains(a)) {
        continue;
      }
      try {
        symbols.createLabel(a, parts[1], SourceType.IMPORTED);
        made++;
      } catch (Exception error) {
        // skip
      }
    }
    println("labels made " + made);

    // Static-field blocks: class struct (static_fields at 0xb8, cctor flag at
    // 0xe4) pointing at a per-class struct of named fields.
    Map<Long, TreeMap<Long, String>> statics = new LinkedHashMap<>();
    for (String line : Files.readAllLines(Paths.get(args[1]))) {
      String[] p = line.split("\t");
      statics.computeIfAbsent(Long.decode(p[0]), k -> new TreeMap<>()).put(Long.decode(p[1]), p[2]);
    }
    DataTypeManager types = currentProgram.getDataTypeManager();
    CategoryPath category = new CategoryPath("/il2cpp");
    int typed = 0;
    for (Map.Entry<Long, TreeMap<Long, String>> entry : statics.entrySet()) {
      Address a = at(entry.getKey());
      if (!currentProgram.getMemory().contains(a)) {
        continue;
      }
      Symbol label = getSymbolAt(a);
      String name = (label != null ? label.getName() : "k_" + Long.toHexString(entry.getKey()))
          .replaceAll("[^A-Za-z0-9_]", "_");
      if (name.length() > 120) {
        name = name.substring(name.length() - 120);
      }
      long size = entry.getValue().lastKey() + 8;
      StructureDataType block = new StructureDataType(category, "S_" + name, (int) size, types);
      for (Map.Entry<Long, String> field : entry.getValue().entrySet()) {
        try {
          block.replaceAtOffset(field.getKey().intValue(), QWordDataType.dataType, 8, field.getValue(), null);
        } catch (Exception error) {
          // overlapping offsets: keep the first
        }
      }
      DataType blockType = types.addDataType(block, DataTypeConflictHandler.REPLACE_HANDLER);
      StructureDataType klass = new StructureDataType(category, "K_" + name, 0xe8, types);
      klass.replaceAtOffset(0xb8, new PointerDataType(blockType, types), 8, "static_fields", null);
      klass.replaceAtOffset(0xe4, IntegerDataType.dataType, 4, "cctor_finished", null);
      DataType klassType = types.addDataType(klass, DataTypeConflictHandler.REPLACE_HANDLER);
      try {
        clearListing(a, a.add(7));
        createData(a, new PointerDataType(klassType, types));
        typed++;
      } catch (Exception error) {
        // skip
      }
    }
    println("typed static blocks " + typed);

    List<Long> list = new ArrayList<>();
    for (String line : Files.readAllLines(Paths.get(args[2]))) {
      if (line.startsWith("0x")) {
        list.add(Long.decode(line.split("\t", 2)[0]));
      }
    }
    Collections.sort(list);
    starts = list.stream().mapToLong(Long::longValue).distinct().toArray();

    Path out = Paths.get(args[4]);
    DecompInterface decompiler = new DecompInterface();
    decompiler.openProgram(currentProgram);
    for (String line : Files.readAllLines(Paths.get(args[3]))) {
      if (line.isBlank()) {
        continue;
      }
      Address entry = at(Long.decode(line.trim()));
      Function function = functionWithBody(entry);
      for (Instruction ins : currentProgram.getListing().getInstructions(function.getBody(), true)) {
        // Calls, and jumps that leave the body (IL2CPP tail calls into
        // shared generic code), become functions of their own.
        boolean call = ins.getFlowType().isCall();
        boolean jump = ins.getFlowType().isJump();
        if (!call && !jump) {
          continue;
        }
        for (Address callee : ins.getFlows()) {
          if (jump && function.getBody().contains(callee)) {
            continue;
          }
          if (getFunctionAt(callee) == null) {
            functionWithBody(callee);
          }
          if (jump && !ins.getFlowType().isConditional()) {
            // A tail call: what auto-analysis would mark.
            ins.setFlowOverride(ghidra.program.model.listing.FlowOverride.CALL_RETURN);
          }
        }
      }
      DecompileResults result = decompiler.decompileFunction(function, 180, monitor);
      String text = result.getDecompiledFunction() != null
          ? result.getDecompiledFunction().getC()
          : "// error: " + result.getErrorMessage();
      Files.writeString(out.resolve(String.format("%x.c", entry.getOffset())), text);
      println("decompiled " + line.trim() + " (" + text.length() + " chars)");
    }
    decompiler.dispose();
  }
}
