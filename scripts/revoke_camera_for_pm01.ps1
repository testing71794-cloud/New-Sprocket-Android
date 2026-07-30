# Optional manual fallback: revoke CAMERA via adb (PM_01 now uses setPermissions in-flow).
param(
    [string]$Device = "ZA222RFQ75"
)

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$pkg = "com.hp.impulse.sprocket"

& $adb -s $Device shell pm revoke $pkg android.permission.CAMERA 2>$null | Out-Null
Start-Sleep -Seconds 2
& $adb -s $Device shell monkey -p $pkg -c android.intent.category.LAUNCHER 1 | Out-Null
Start-Sleep -Seconds 3
Write-Host "CAMERA revoked; $pkg foregrounded on $Device"
