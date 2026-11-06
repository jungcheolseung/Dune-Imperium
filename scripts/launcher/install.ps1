# Dune Imperium: install or update the game on Windows with one line,
# without git and without a Python of your own (docs/remote-play-host-guide.md,
# section "one-line install"). In a PowerShell window:
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
#
# Everything goes in one folder, "%USERPROFILE%\Dune Imperium" unless
# DUNE_IMPERIUM_HOME names another: the public repository's source snapshot,
# uv, Python, the packages, and later the saves and the launcher's settings.
# PATH is not changed and Python is not registered, so deleting the folder
# removes the game. Running the same line again updates the game and keeps
# saves\, local\, checkpoints\ and assets\. scripts/launcher/install.sh is
# the macOS twin; keep the two in step.
#
# For tests and special cases:
#   DUNE_IMPERIUM_HOME     the install folder
#   DUNE_IMPERIUM_ARCHIVE  the source snapshot, a .zip URL (file:/// works)
#   DUNE_IMPERIUM_NO_OPEN  1: do not open the folder and the launcher at the end
#
# ASCII only: Windows PowerShell 5.1 reads a file without a BOM in the
# console's code page, where a misread byte can even become a quote.
# Failures throw instead of calling exit: pasted as "irm ... | iex" into an
# open window, exit would close that window before its message is read.

function Install-DuneImperium {
    # The uv release this installs; keep it at the uv that wrote uv.lock.
    $uvVersion = '0.11.24'
    $archiveUrl = 'https://github.com/jungcheolseung/Dune-Imperium/archive/refs/heads/master.zip'
    $appName = 'Dune Imperium Server'

    # Native programs report through $LASTEXITCODE; with 'Stop', Windows
    # PowerShell 5.1 would turn their standard error into a terminating error.
    $ErrorActionPreference = 'Continue'
    # 5.1's progress bar slows Invoke-WebRequest down many times over.
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $root = $env:DUNE_IMPERIUM_HOME
    if (-not $root) { $root = Join-Path $env:USERPROFILE 'Dune Imperium' }
    $archive = $env:DUNE_IMPERIUM_ARCHIVE
    if (-not $archive) { $archive = $archiveUrl }
    $runtime = Join-Path $root 'runtime'
    $marker = Join-Path $runtime 'install-marker.txt'

    # Only a folder this script made, or an empty or missing one: an update
    # replaces the snapshot's folders (src\, docs\ ...) wholesale.
    if (Test-Path -LiteralPath (Join-Path $root '.git')) {
        throw "$root is a git checkout; update it with git pull instead."
    }
    if ((Test-Path -LiteralPath $root) -and -not (Test-Path -LiteralPath $marker) -and
        (Get-ChildItem -LiteralPath $root -Force | Select-Object -First 1)) {
        throw "$root already holds other files. Empty it, or name another folder in DUNE_IMPERIUM_HOME."
    }
    [IO.Directory]::CreateDirectory($runtime) | Out-Null
    if (-not (Test-Path -LiteralPath $marker)) {
        [IO.File]::WriteAllText($marker, "Made by scripts/launcher/install.ps1; an update may replace this folder's files.`r`n")
    }

    # An update under a running launcher would mix old and new code (and
    # Windows keeps its files locked); the launcher's own single-instance
    # lock tells (instance.py).
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $python) {
        & $python -c 'import sys; from dune_imperium.launcher.instance import InstanceLock; sys.exit(0 if InstanceLock().acquire() else 3)'
        if ($LASTEXITCODE -eq 3) {
            throw 'The server launcher is open. Close its window, then run the same line again.'
        }
    }

    Write-Host "1/4 uv $uvVersion"
    $uvDir = Join-Path $runtime 'bin'
    $uv = Join-Path $uvDir 'uv.exe'
    $current = $null
    if (Test-Path -LiteralPath $uv) { $current = ((& $uv --version) -split ' ')[1] }
    if ($current -ne $uvVersion) {
        $installer = Join-Path $runtime 'uv-installer.ps1'
        Invoke-WebRequest -UseBasicParsing -Uri "https://astral.sh/uv/$uvVersion/install.ps1" -OutFile $installer -ErrorAction Stop
        $env:UV_UNMANAGED_INSTALL = $uvDir
        try {
            & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy ByPass -File $installer
            $code = $LASTEXITCODE
        } finally {
            Remove-Item Env:UV_UNMANAGED_INSTALL -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
        }
        if ($code -ne 0 -or -not (Test-Path -LiteralPath $uv)) { throw 'Could not install uv.' }
    }

    Write-Host '2/4 Downloading the game'
    $work = Join-Path $runtime 'download'
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction Stop }
    $new = Join-Path $work 'new'
    [IO.Directory]::CreateDirectory($new) | Out-Null
    $zip = Join-Path $work 'game.zip'
    if ($archive -like 'file:*') {
        Copy-Item -LiteralPath ([Uri]$archive).LocalPath -Destination $zip -ErrorAction Stop
    } else {
        Invoke-WebRequest -UseBasicParsing -Uri $archive -OutFile $zip -ErrorAction Stop
    }
    # Much faster than Expand-Archive on 5.1.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $new)
    $tops = @(Get-ChildItem -LiteralPath $new -Force)
    if ($tops.Count -ne 1 -or -not $tops[0].PSIsContainer) { throw 'The downloaded game files have an unexpected layout.' }
    $snapshot = $tops[0].FullName
    foreach ($required in 'pyproject.toml', 'uv.lock', 'src\dune_imperium') {
        if (-not (Test-Path -LiteralPath (Join-Path $snapshot $required))) {
            throw 'The downloaded game files have an unexpected layout.'
        }
    }
    # Each top-level entry of the snapshot replaces the old one. What the
    # snapshot never holds (all git-ignored) stays: the saves, the launcher's
    # settings, networks, pictures, the environment and this runtime.
    $keep = @('runtime', 'saves', 'local', 'checkpoints', 'assets', 'tmp', '.venv', "$appName.lnk")
    foreach ($entry in Get-ChildItem -LiteralPath $snapshot -Force) {
        if ($keep -contains $entry.Name) { continue }
        $target = Join-Path $root $entry.Name
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop }
        Move-Item -LiteralPath $entry.FullName -Destination $target -ErrorAction Stop
    }
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host '3/4 Installing Python and the packages (a few minutes the first time)'
    # uv's Python, its cache and nothing else in this folder; restored after,
    # in case this runs in the user's own PowerShell session.
    $settings = @{
        UV_PYTHON_INSTALL_DIR = (Join-Path $runtime 'python')
        UV_CACHE_DIR = (Join-Path $runtime 'cache')
        UV_PYTHON_INSTALL_BIN = '0'
        UV_PYTHON_INSTALL_REGISTRY = '0'
        UV_NO_MODIFY_PATH = '1'
        VIRTUAL_ENV = $null
        CONDA_PREFIX = $null
        PYTHONHOME = $null
        PYTHONPATH = $null
    }
    $saved = @{}
    foreach ($name in $settings.Keys) {
        $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
    }
    Push-Location -LiteralPath $root
    try {
        & $uv sync --locked --no-dev --extra ui --managed-python
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not install the packages. Check the internet connection and run the same line again.'
        }
        Write-Host '4/4 Making the launcher shortcut'
        & $python -m dune_imperium.launcher.cli --make-shortcut
        if ($LASTEXITCODE -ne 0) { throw 'Could not make the launcher shortcut.' }
    } finally {
        Pop-Location
        foreach ($name in $saved.Keys) {
            [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process')
        }
    }

    Write-Host ''
    Write-Host "Done: $root"
    Write-Host "From now on, double-click '$appName' in this folder (you can pin it to the taskbar)."
    Write-Host 'To update, run the same line again. To remove the game, delete the folder.'
    if ($env:DUNE_IMPERIUM_NO_OPEN -ne '1') {
        Invoke-Item -LiteralPath $root
        Start-Process -FilePath (Join-Path $root '.venv\Scripts\dune-imperium-launcher.exe') -WorkingDirectory $root
    }
}

try {
    Install-DuneImperium
} catch {
    Write-Host ''
    Write-Host "Install stopped: $($_.Exception.Message)" -ForegroundColor Red
}
