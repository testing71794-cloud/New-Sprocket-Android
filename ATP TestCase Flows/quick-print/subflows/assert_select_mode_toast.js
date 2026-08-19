// Maestro JS HTTP client — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = MAESTRO_DEVICE_UDID || '';
var expect = TOAST_EXPECT || 'present';
var action = TOAST_ACTION || 'poll';
var path = '/toast';
if (action === 'arm') {
  path = '/toast/arm';
} else if (action === 'result') {
  path = '/toast/result';
}
if (expect === 'present' && action !== 'arm' && output.qp005ToastOk === '1') {
  // already caught from a11y
} else {
  var url = 'http://127.0.0.1:8765' + path + '?expect=' + expect + '&serial=' + encodeURIComponent(serial);
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e) {
    data = { ok: false, error: String(response.body || e) };
  }
  if (action === 'arm') {
    output.qp005ToastArmed = data.armed ? '1' : '0';
  } else {
    output.qp005ToastOk = data.ok ? '1' : '0';
    output.qp005ToastFound = data.found ? '1' : '0';
    output.qp005ToastText = data.text || data.error || '';
  }
}
