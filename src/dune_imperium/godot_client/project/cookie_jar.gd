extends RefCounted

# Browser-equivalent origin/path scoping. Tokens never enter URLs or logs.
var entries: Array = []


func remember(origin: String, header: String, now: float) -> void:
	var parts = header.split(";")
	var pair = parts[0].strip_edges()
	var divider = pair.find("=")
	if divider <= 0:
		return
	var name = pair.left(divider)
	var value = pair.substr(divider + 1)
	if name.contains("\r") or name.contains("\n") or value.contains("\r") or value.contains("\n"):
		return
	var path = "/"
	var expires = -1.0
	var secure = false
	for part in parts.slice(1):
		var attribute = part.strip_edges()
		var key = attribute.get_slice("=", 0).to_lower()
		var argument = attribute.substr(attribute.find("=") + 1)
		if key == "path" and argument.begins_with("/"):
			path = argument
		elif key == "max-age" and argument.is_valid_int():
			expires = now + int(argument)
		elif key == "secure":
			secure = true
	entries = entries.filter(func(cookie): return not (cookie.origin == origin and cookie.name == name and cookie.path == path))
	if not value.is_empty() and (expires < 0 or expires > now):
		entries.append({"origin": origin, "path": path, "name": name, "value": value, "expires": expires, "secure": secure})


func header(origin: String, path: String, now: float) -> String:
	var pairs: PackedStringArray = []
	for cookie in entries:
		if not cookie is Dictionary or not cookie.has_all(["origin", "path", "name", "value", "expires", "secure"]):
			continue
		if cookie.origin != origin or (float(cookie.expires) >= 0 and float(cookie.expires) <= now):
			continue
		if cookie.secure and not origin.begins_with("https://"):
			continue
		if path != cookie.path and not path.begins_with(str(cookie.path).trim_suffix("/") + "/"):
			continue
		var pair = str(cookie.name) + "=" + str(cookie.value)
		if not pair.contains("\r") and not pair.contains("\n"):
			pairs.append(pair)
	return "; ".join(pairs)
