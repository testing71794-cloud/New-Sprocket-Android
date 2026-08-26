// Fill Select Mode to 10 photos via helper (date-grouped grid; %-taps miss cells).
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
  '&want=10&kind=photos';
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e2) {
    data = { ok: false, error: String(response.body || e2) };
  }
  output.qpSelectUntilOk = data.ok ? '1' : '0';
  output.qpSelectPhotos = String(data.photos || 0);
  output.qpSelectText = data.text || data.error || '';
} catch (e) {
  output.qpSelectUntilOk = '0';
  output.qpSelectPhotos = '0';
  output.qpSelectText = String(e);
}
