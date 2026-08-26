// Select 1 photo + 1 video via helper tiles (date-grouped grid; %-taps miss).
// See: https://docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = '';
try {
  if (typeof MAESTRO_DEVICE_UDID !== 'undefined' && MAESTRO_DEVICE_UDID) {
    serial = String(MAESTRO_DEVICE_UDID);
  }
} catch (e) {
  serial = '';
}
var url = 'http://127.0.0.1:8765/select-until?serial=' + encodeURIComponent(serial) +
  '&want=1&kind=mixed';
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e2) {
    data = { ok: false, error: String(response.body || e2) };
  }
  output.qpSelectMixedOk = data.ok ? '1' : '0';
  output.qpSelectPhotos = String(data.photos || 0);
  output.qpSelectVideos = String(data.videos || 0);
  output.qpSelectText = data.text || data.error || '';
} catch (e) {
  output.qpSelectMixedOk = '0';
  output.qpSelectPhotos = '0';
  output.qpSelectVideos = '0';
  output.qpSelectText = String(e);
}
