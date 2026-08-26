// Create Pictures/MaestroEmpty so Select Gallery has a 0-photo folder.
// See: https://docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = '';
try {
  if (typeof MAESTRO_DEVICE_UDID !== 'undefined' && MAESTRO_DEVICE_UDID) {
    serial = String(MAESTRO_DEVICE_UDID);
  }
} catch (e) {
  serial = '';
}
var url = 'http://127.0.0.1:8765/ensure-empty-album?serial=' + encodeURIComponent(serial);
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e2) {
    data = { ok: false, error: String(response.body || e2) };
  }
  output.qpEmptyAlbum = data.name || 'MaestroEmpty';
  output.qpEmptyOk = data.ok ? '1' : '0';
} catch (e) {
  output.qpEmptyAlbum = 'MaestroEmpty';
  output.qpEmptyOk = '0';
}
