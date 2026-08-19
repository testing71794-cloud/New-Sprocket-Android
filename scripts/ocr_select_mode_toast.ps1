param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [int]$BottomPercent = 0
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]

function Await-WinRt {
    param($Operation, [type]$ResultType)
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    $netTask = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $ocr) {
    Write-Output 'OCR_ENGINE_UNAVAILABLE'
    exit 2
}

$resolved = (Resolve-Path $ImagePath).Path
if ($BottomPercent -gt 0 -and $BottomPercent -lt 100) {
    Add-Type -AssemblyName System.Drawing | Out-Null
    $src = [System.Drawing.Image]::FromFile($resolved)
    $cut = [int]($src.Height * $BottomPercent / 100)
    $y = $src.Height - $cut
    $crop = New-Object System.Drawing.Bitmap $src.Width, $cut
    $g = [System.Drawing.Graphics]::FromImage($crop)
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, $src.Width, $cut), (New-Object System.Drawing.Rectangle 0, $y, $src.Width, $cut), [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()
    $src.Dispose()
    $cropPath = [System.IO.Path]::Combine([System.IO.Path]::GetDirectoryName($resolved), ([System.IO.Path]::GetFileNameWithoutExtension($resolved) + "_bottom.png"))
    $crop.Save($cropPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $crop.Dispose()
    $resolved = $cropPath
}

$file = Await-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($resolved)) ([Windows.Storage.StorageFile])
$stream = Await-WinRt ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await-WinRt ($ocr.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
Write-Output $result.Text
exit 0
