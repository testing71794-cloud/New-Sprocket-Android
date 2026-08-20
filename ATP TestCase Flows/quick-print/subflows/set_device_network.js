// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = MAESTRO_DEVICE_UDID || '';
var state = NET_STATE || 'on';
var url = 'http://127.0.0.1:8765/network?state=' + encodeURIComponent(state) + '&serial=' + encodeURIComponent(serial);
try {
  var response = http.get(url);
  var data = json(response.body);
  output.qpNetOk = data.ok ? '1' : '0';
} catch (e) {
  output.qpNetOk = '0';
}
