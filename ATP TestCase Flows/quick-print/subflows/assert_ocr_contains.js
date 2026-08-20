// Maestro JS HTTP — docs.maestro.dev/maestro-flows/javascript/make-http-requests
var serial = '';
try {
  if (typeof MAESTRO_DEVICE_UDID !== 'undefined' && MAESTRO_DEVICE_UDID) {
    serial = String(MAESTRO_DEVICE_UDID);
  }
} catch (e) {
  serial = '';
}
var needle = OCR_NEEDLE || 'maximum of 10';
var seconds = OCR_SECONDS || '4';
var expect = OCR_EXPECT || 'present';
var action = OCR_ACTION || 'poll';
var path = '/ocr';
if (action === 'arm') {
  path = '/ocr/arm';
} else if (action === 'result') {
  path = '/ocr/result';
}
try {
  var url = 'http://127.0.0.1:8765' + path +
    '?needle=' + encodeURIComponent(needle) +
    '&seconds=' + encodeURIComponent(seconds) +
    '&expect=' + encodeURIComponent(expect) +
    '&serial=' + encodeURIComponent(serial);
  var response = http.get(url);
  var data = {};
  try {
    data = json(response.body);
  } catch (e) {
    data = { ok: false, error: String(response.body || e) };
  }
  if (action === 'arm') {
    output.qpOcrArmed = data.armed ? '1' : '0';
  } else if (action === 'result' && output.qpOcrOk === '1') {
    output.qpOcrText = data.text || output.qpOcrText || '';
  } else {
    output.qpOcrOk = data.ok ? '1' : '0';
    output.qpOcrText = data.text || data.error || '';
  }
} catch (e) {
  if (action === 'arm') {
    output.qpOcrArmed = '0';
  } else if (output.qpOcrOk !== '1') {
    output.qpOcrOk = '0';
    output.qpOcrText = String(e);
  }
}
