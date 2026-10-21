extends Node

# A ring carries the public counters a snapshot is identified by
# (sessions.py _doorbell); the table decides whether its picture is stale.
signal changed(bell: Dictionary)
signal connection_changed(online: bool)
signal closed

var api: Node
var game_id = ""
var client = HTTPClient.new()
var requested = false
var buffer = PackedByteArray()
var retry_at = 0
var live = false
var last_event: Dictionary = {}
# The origin this connection was opened to; its request carries that
# origin's cookies only, even if the table switches servers meanwhile.
var origin = ""
var started_at = 0
# The server writes a heartbeat every 15 s (events.py): a stream silent for
# longer than two of them is a dead connection, however its status reads.
const SILENT_MSEC = 35000
var heard_at = 0


func start(id: String) -> void:
	stop()
	game_id = id
	started_at = Time.get_ticks_msec()
	_connect()


func stop() -> void:
	client.close()
	game_id = ""
	buffer = PackedByteArray()
	requested = false
	last_event.clear()
	_set_live(false)


func _set_live(value: bool) -> void:
	if live != value:
		live = value
		connection_changed.emit(value)


func _connect() -> void:
	origin = api.base_url
	heard_at = Time.get_ticks_msec()
	var url = origin
	var secure = url.begins_with("https://")
	var authority = url.trim_prefix("https://").trim_prefix("http://")
	var host = authority.get_slice(":", 0)
	var port = int(authority.get_slice(":", 1)) if authority.contains(":") else (443 if secure else 80)
	if authority.begins_with("["):
		host = authority.get_slice("]", 0).trim_prefix("[")
		port = int(authority.get_slice("]:", 1)) if authority.contains("]:") else (443 if secure else 80)
	requested = false
	buffer = PackedByteArray()
	var error = client.connect_to_host(host, port, TLSOptions.client() if secure else null)
	if error != OK:
		_retry()


func _retry() -> void:
	client.close()
	requested = false
	buffer = PackedByteArray()
	retry_at = Time.get_ticks_msec() + 1500
	_set_live(false)


func _process(_delta: float) -> void:
	if game_id.is_empty():
		return
	if client.get_status() == HTTPClient.STATUS_DISCONNECTED:
		if Time.get_ticks_msec() >= retry_at:
			_connect()
		return
	if client.poll() != OK:
		_retry()
		return
	var state = client.get_status()
	if state == HTTPClient.STATUS_CONNECTED:
		if requested:
			_retry()
			return
		var path = "/games/" + game_id + "/events"
		if origin != api.base_url:
			_retry()
			return
		var headers = api.request_headers(origin, path)
		headers.append("Accept: text/event-stream")
		if client.request(HTTPClient.METHOD_GET, path, headers) != OK:
			_retry()
			return
		requested = true
	elif state == HTTPClient.STATUS_BODY:
		if client.get_response_code() != 200:
			_retry()
			return
		var chunk = client.read_response_body_chunk()
		if not chunk.is_empty():
			heard_at = Time.get_ticks_msec()
			_consume(chunk)
		elif Time.get_ticks_msec() - heard_at > SILENT_MSEC:
			_retry()
	elif state in [HTTPClient.STATUS_CANT_RESOLVE, HTTPClient.STATUS_CANT_CONNECT, HTTPClient.STATUS_CONNECTION_ERROR, HTTPClient.STATUS_TLS_HANDSHAKE_ERROR]:
		_retry()


func _consume(chunk: PackedByteArray) -> void:
	buffer.append_array(chunk)
	if buffer.size() > 65536:
		_retry()
		return
	while true:
		var boundary = -1
		for index in range(maxi(0, buffer.size() - 1)):
			if buffer[index] == 10 and buffer[index + 1] == 10:
				boundary = index
				break
		if boundary < 0:
			return
		var frame = buffer.slice(0, boundary).get_string_from_utf8()
		buffer = buffer.slice(boundary + 2)
		# Live once the stream speaks (its hello, a heartbeat), not when its
		# headers arrive: a buffering proxy sends those and holds the body.
		_set_live(true)
		if frame.contains("event: closed"):
			stop()
			closed.emit()
			return
		for line in frame.split("\n"):
			if line.begins_with("data:"):
				var data = JSON.parse_string(line.substr(5).strip_edges())
				if data is Dictionary and data != last_event:
					if not last_event.is_empty() and int(data.get("seq", -1)) <= int(last_event.get("seq", -1)):
						continue
					last_event = data
					changed.emit(data)
