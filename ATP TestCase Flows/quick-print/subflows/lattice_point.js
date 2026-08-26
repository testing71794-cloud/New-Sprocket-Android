// Next Select Mode thumbnail for a 3-col lattice (skips Cancel / Print Preview).
// See: https://docs.maestro.dev/maestro-flows/javascript/manage-data-and-states
var i = parseInt(String(output.qpIdx || '0'), 10);
if (isNaN(i) || i < 0) {
  i = 0;
}
var xs = [17, 50, 83];
var ys = [26, 40, 54, 66];
var page = Math.floor(i / 12);
var local = i % 12;
var yOff = (page % 2) * 4;
var x = xs[local % 3];
var y = ys[Math.floor(local / 3)] + yOff;
if (y > 72) {
  y = 72;
}
output.qpPoint = x + '%,' + y + '%';
output.qpNeedSwipe = (local === 11) ? '1' : '0';
output.qpIdx = String(i + 1);
