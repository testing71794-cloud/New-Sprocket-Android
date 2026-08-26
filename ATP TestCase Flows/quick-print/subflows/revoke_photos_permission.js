// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = MAESTRO_DEVICE_UDID || '';
var url = 'http://127.0.0.1:8765/revoke-photos?serial=' + encodeURIComponent(serial);
var response = http.get(url);
var data = {};
try {
  data = json(response.body);
} catch (e) {
  data = { ok: false, error: String(response.body || e) };
}
output.qpRevokeOk = data.ok ? '1' : '0';
