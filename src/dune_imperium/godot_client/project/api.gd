extends Node

signal texture_ready(path: String, texture: Texture2D)

var base_url = "http://127.0.0.1:8000"
var textures: Dictionary = {}
var pending: Dictionary = {}
var image_queue: Array[String] = []
var image_workers = 0


func call_json(method: int, path: String, data: Dictionary = {}) -> Dictionary:
	var request = HTTPRequest.new()
	request.timeout = 30.0
	add_child(request)
	var body = "" if method == HTTPClient.METHOD_GET else JSON.stringify(data)
	var error = request.request(base_url + path, ["Content-Type: application/json"], method, body)
	if error != OK:
		request.queue_free()
		return {"ok": false, "code": 0, "data": {"detail": "서버에 연결하지 못했습니다."}}
	var result = await request.request_completed
	request.queue_free()
	var parsed = JSON.parse_string(result[3].get_string_from_utf8())
	var response = parsed if parsed is Dictionary or parsed is Array else {}
	var success = result[0] == HTTPRequest.RESULT_SUCCESS and result[1] >= 200 and result[1] < 300
	return {"ok": success, "code": result[1], "data": response}


func texture(path: String) -> Texture2D:
	if path.is_empty():
		return null
	if textures.has(path):
		return textures[path]
	if not pending.has(path):
		pending[path] = true
		image_queue.append(path)
		_pump_images()
	return null


func _pump_images() -> void:
	while image_workers < 3 and not image_queue.is_empty():
		image_workers += 1
		_download_image(image_queue.pop_front())


func _download_image(path: String) -> void:
	var request = HTTPRequest.new()
	request.timeout = 30.0
	request.body_size_limit = 32 * 1024 * 1024
	add_child(request)
	var error = request.request(base_url + path)
	if error == OK:
		var result = await request.request_completed
		if result[0] == HTTPRequest.RESULT_SUCCESS and result[1] == 200:
			var image = Image.new()
			var extension = path.get_slice("?", 0).get_extension().to_lower()
			if extension == "webp":
				error = image.load_webp_from_buffer(result[3])
			elif extension in ["jpg", "jpeg"] or path.begins_with("/board-image"):
				error = image.load_jpg_from_buffer(result[3])
			else:
				error = image.load_png_from_buffer(result[3])
			if error == OK:
				var limit = 3072 if path.begins_with("/board-image") else 900
				var longest = maxi(image.get_width(), image.get_height())
				if longest > limit:
					var ratio = float(limit) / longest
					image.resize(maxi(1, roundi(image.get_width() * ratio)), maxi(1, roundi(image.get_height() * ratio)), Image.INTERPOLATE_LANCZOS)
				var loaded = ImageTexture.create_from_image(image)
				textures[path] = loaded
				texture_ready.emit(path, loaded)
	request.queue_free()
	image_workers -= 1
	_pump_images()
