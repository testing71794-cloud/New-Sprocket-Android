// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = '';
try {
  if (typeof MAESTRO_DEVICE_UDID !== 'undefined' && MAESTRO_DEVICE_UDID) {
    serial = String(MAESTRO_DEVICE_UDID);
  }
} catch (e) {
  serial = '';
}
var needle = OCR_NEEDLE || 'maximum of 10 photos allowed,maximum of 10,10 photos allowed';
var seconds = OCR_SECONDS || '6';
var url = 'http://127.0.0.1:8765/tap-max-limit?serial=' + encodeURIComponent(serial) +
  '&needle=' + encodeURIComponent(needle) +
  '&seconds=' + encodeURIComponent(seconds);
try {
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e) {
    data = { ok: false, error: String(response.body || e) };
  }
  output.qpMaxTapOk = data.tapped ? '1' : '0';
  output.qpOcrOk = data.ok ? '1' : '0';
  output.qpOcrText = data.text || data.error || '';
  output.qpTapX = String(data.x || 0);
  output.qpTapY = String(data.y || 0);
} catch (e) {
  output.qpMaxTapOk = '0';
  output.qpOcrOk = output.qpOcrOk || '0';
  output.qpOcrText = String(e);
}
