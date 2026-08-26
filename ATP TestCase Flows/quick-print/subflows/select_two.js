// Select 2 items of any type (2 photos, 2 videos, or 1+1). %-taps miss date-grouped tiles.
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
  '&want=2&kind=any';
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e2) {
    data = { ok: false, error: String(response.body || e2) };
  }
  output.qpSelectTwoOk = data.ok ? '1' : '0';
  output.qpSelectPhotos = String(data.photos || 0);
  output.qpSelectVideos = String(data.videos || 0);
  output.qpSelectText = data.text || data.error || '';
} catch (e) {
  output.qpSelectTwoOk = '0';
  output.qpSelectPhotos = '0';
  output.qpSelectVideos = '0';
  output.qpSelectText = String(e);
}
