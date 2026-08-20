// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = MAESTRO_DEVICE_UDID || '';
var x = output.qpTapX || '0';
var y = output.qpTapY || '0';
var url = 'http://127.0.0.1:8765/tap-xy?serial=' + encodeURIComponent(serial) +
  '&x=' + encodeURIComponent(x) +
  '&y=' + encodeURIComponent(y);
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e) {
    data = { ok: false, error: String(response.body || e) };
  }
  output.qpTapXyOk = data.ok ? '1' : '0';
} catch (e) {
  output.qpTapXyOk = '0';
}
