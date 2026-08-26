# One-shot: swipe printer carousel toward HP Sprocket 200 via adb input.
param(
  [string]$Serial = "ZA222RFQ75",
  [ValidateSet("to200","back")]
  [string]$Dir = "to200"
)
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
# Image band ~y=959 on 1080x2400; finger-right brings left chip (200) toward center when Sense is selected.
if ($Dir -eq "to200") {
  & $adb -s $Serial shell input swipe 300 960 780 960 450
} else {
  & $adb -s $Serial shell input swipe 780 960 300 960 450
}
Start-Sleep -Milliseconds 800
