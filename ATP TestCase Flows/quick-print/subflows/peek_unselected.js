// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = MAESTRO_DEVICE_UDID || '';
var url = 'http://127.0.0.1:8765/peek-unselected?serial=' + encodeURIComponent(serial);
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e) {
    data = { ok: false, error: String(response.body || e) };
  }
  output.qpTapX = String(data.x || 0);
  output.qpTapY = String(data.y || 0);
  output.qpPeekOk = data.ok ? '1' : '0';
} catch (e) {
  output.qpTapX = '0';
  output.qpTapY = '0';
  output.qpPeekOk = '0';
}
