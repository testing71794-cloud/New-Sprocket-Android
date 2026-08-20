// Optional dump-based overflow tap. Must not throw if the helper is down.
// See: https://docs.maestro.dev/maestro-flows/javascript/make-http-requests
output.qpOverflowOk = '0';
try {
    var serial = MAESTRO_DEVICE_UDID || '';
    var url = 'http://127.0.0.1:8765/tap?kind=overflow&serial=' + encodeURIComponent(serial);
    var response = http.get(url);
    var data = {};
    try {
        data = json(response.body);
    } catch (e) {
        data = { ok: false };
    }
    output.qpOverflowOk = data.ok ? '1' : '0';
} catch (e) {
    output.qpOverflowOk = '0';
}
