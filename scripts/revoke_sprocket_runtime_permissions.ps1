# Revoke Sprocket runtime permissions so PM_* flows show OS permission dialogs.
# Usage: .\scripts\revoke_sprocket_runtime_permissions.ps1 [-Device SERIAL] [-SkipClear]
param(
    [string]$Device = "",
    [switch]$SkipClear
)

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$pkg = "com.hp.impulse.sprocket"
$adbArgs = @()
if ($Device) { $adbArgs = @("-s", $Device) }

$perms = @(
    "android.permission.CAMERA",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.NEARBY_WIFI_DEVICES",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_EXTERNAL_STORAGE"
)

foreach ($p in $perms) {
    & $adb @adbArgs shell pm revoke $pkg $p 2>$null | Out-Null
}
if (-not $SkipClear) {
    & $adb @adbArgs shell pm clear $pkg | Out-Null
}
$target = if ($Device) { $Device } else { "default device" }
$cleared = if ($SkipClear) { "revoked only" } else { "revoked and cleared" }
Write-Host "$cleared $pkg on $target"
