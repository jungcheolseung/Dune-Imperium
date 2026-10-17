extends Node

signal texture_ready(path: String, texture: Texture2D)

var base_url = "http://127.0.0.1:8000"
var textures: Dictionary = {}
var pending: Dictionary = {}
var image_queue: Array[Dictionary] = []
var image_workers = 0
const CookieJar = preload("res://cookie_jar.gd")
const COOKIE_FILE = "res://../../../../local/godot-cookies.json"
var cookies = CookieJar.new()
var cookie_file = COOKIE_FILE


func _ready() -> void:
	if FileAccess.file_exists(cookie_file):
		var data = JSON.parse_string(FileAccess.get_file_as_string(cookie_file))
		if data is Array:
			cookies.entries = data.filter(func(cookie): return cookie is Dictionary and cookie.has_all(["origin", "path", "name", "value", "expires", "secure"]))


func headers(path: String) -> PackedStringArray:
	var result: PackedStringArray = ["Content-Type: application/json"]
	var cookie = cookies.header(base_url, path.get_slice("?", 0), Time.get_unix_time_from_system())
	if not cookie.is_empty():
		result.append("Cookie: " + cookie)
	return result


func _remember_headers(response: PackedStringArray, origin: String) -> void:
	var changed = false
	for header in response:
		if header.to_lower().begins_with("set-cookie:"):
			cookies.remember(origin, header.substr(11).strip_edges(), Time.get_unix_time_from_system())
			changed = true
	if changed:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(cookie_file.get_base_dir()))
		var file = FileAccess.open(cookie_file, FileAccess.WRITE)
		if file != null:
			file.store_string(JSON.stringify(cookies.entries))


func call_json(method: int, path: String, data: Dictionary = {}) -> Dictionary:
	var request = HTTPRequest.new()
	request.timeout = 30.0
	add_child(request)
	var body = "" if method == HTTPClient.METHOD_GET else JSON.stringify(data)
	var origin = base_url
	request.max_redirects = 0
	var error = request.request(origin + path, headers(path), method, body)
	if error != OK:
		request.queue_free()
		return {"ok": false, "code": 0, "data": {"detail": "서버에 연결하지 못했습니다."}}
	var result = await request.request_completed
	request.queue_free()
	_remember_headers(result[2], origin)
	# Closing/replacing an owned server can finish a poll with an empty body.
	# A failed connection is a UI error, not a JSON parser engine error.
	var json = JSON.new()
	var parsed: Variant = null
	if not result[3].is_empty() and json.parse(result[3].get_string_from_utf8()) == OK:
		parsed = json.data
	var valid = parsed is Dictionary or parsed is Array
	var response = parsed if valid else {"detail": "서버 응답을 읽지 못했습니다."}
	var success = valid and result[0] == HTTPRequest.RESULT_SUCCESS and result[1] >= 200 and result[1] < 300
	return {"ok": success, "code": result[1], "data": response}


func texture(path: String) -> Texture2D:
	if path.is_empty():
		return null
	var key = base_url + path
	if textures.has(key):
		return textures[key]
	if not pending.has(key):
		pending[key] = true
		image_queue.append({"origin": base_url, "path": path})
		_pump_images()
	return null


func _pump_images() -> void:
	while image_workers < 3 and not image_queue.is_empty():
		image_workers += 1
		var job = image_queue.pop_front()
		_download_image(job.origin, job.path)


func _download_image(origin: String, path: String) -> void:
	var request = HTTPRequest.new()
	request.timeout = 30.0
	request.body_size_limit = 32 * 1024 * 1024
	add_child(request)
	var error = request.request(origin + path)
	if error == OK:
		var result = await request.request_completed
		if result[0] == HTTPRequest.RESULT_SUCCESS and result[1] == 200:
			var image = Image.new()
			# Image endpoints have no extension; choose the decoder from the bytes.
			var bytes: PackedByteArray = result[3]
			error = ERR_FILE_UNRECOGNIZED
			if bytes.size() >= 12 and bytes.slice(0, 4).get_string_from_ascii() == "RIFF" and bytes.slice(8, 12).get_string_from_ascii() == "WEBP":
				error = image.load_webp_from_buffer(bytes)
			elif bytes.size() >= 3 and bytes[0] == 255 and bytes[1] == 216 and bytes[2] == 255:
				error = image.load_jpg_from_buffer(bytes)
			elif bytes.size() >= 8 and bytes.slice(0, 8) == PackedByteArray([137, 80, 78, 71, 13, 10, 26, 10]):
				error = image.load_png_from_buffer(bytes)
			if error == OK:
				var limit = 3072 if path.begins_with("/board-image") else 900
				var longest = maxi(image.get_width(), image.get_height())
				if longest > limit:
					var ratio = float(limit) / longest
					image.resize(maxi(1, roundi(image.get_width() * ratio)), maxi(1, roundi(image.get_height() * ratio)), Image.INTERPOLATE_LANCZOS)
				var loaded = ImageTexture.create_from_image(image)
				textures[origin + path] = loaded
				if origin == base_url:
					texture_ready.emit(path, loaded)
	request.queue_free()
	pending.erase(origin + path)
	image_workers -= 1
	_pump_images()
