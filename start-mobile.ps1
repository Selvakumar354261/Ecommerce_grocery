param(
    [string]$DeviceId,
    [switch]$Rebuild,
    [ValidateSet('delivery-mobile-flutter','customer-mobile-flutter')]
    [string]$AppDirectory = 'delivery-mobile-flutter'
)
$ErrorActionPreference = 'Stop'
$appRoot = Join-Path $PSScriptRoot $AppDirectory
$adb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$flutter = 'C:\Develop\flutter\bin\flutter.bat'
if (-not (Test-Path $adb)) { throw 'Android platform-tools (adb) was not found.' }
$devices = @(& $adb devices | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
if (-not $DeviceId) {
    if ($devices.Count -ne 1) { throw 'Connect and authorize one Android phone, or pass -DeviceId SERIAL.' }
    $DeviceId = $devices[0]
}
if ($DeviceId -notin $devices) { throw 'The selected phone is not connected and authorized.' }
# USB forwarding keeps the installed app independent of changing Wi-Fi IP addresses.
& $adb -s $DeviceId reverse tcp:8080 tcp:8080
if ($LASTEXITCODE -ne 0) { throw 'Could not forward the server port to the phone.' }
try { Invoke-RestMethod 'http://127.0.0.1:8080/api/v1/health' -TimeoutSec 10 | Out-Null }
catch { throw 'The backend is not ready on port 8080. Start Docker services and try again.' }
$files = @(Get-ChildItem "$appRoot\lib", "$appRoot\android" -File -Recurse | Where-Object {
    $_.FullName -notmatch '\\(build|\.gradle|\.kotlin|\.cxx)\\' -and $_.Name -ne 'local.properties'
}) + @(Get-Item "$appRoot\pubspec.yaml", "$appRoot\pubspec.lock")
if (Test-Path "$appRoot\assets") { $files += Get-ChildItem "$appRoot\assets" -File -Recurse }
$inputText = 'usb-localhost-8080-v1;' + (($files | Sort-Object FullName | ForEach-Object {
    $_.FullName.Substring($appRoot.Length) + ':' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash
}) -join ';')
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $fingerprint = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($inputText))) }
finally { $sha.Dispose() }
$marker = Join-Path $appRoot '.dart_tool\mobile-install.json'
$saved = $null
if (Test-Path $marker) { try { $saved = Get-Content $marker -Raw | ConvertFrom-Json } catch {} }
$package = if ($AppDirectory -eq 'customer-mobile-flutter') { 'in.chinnu.chinnu_customer' } else { 'in.chinnu.chinnu_delivery' }
$installed = & $adb -s $DeviceId shell pm path $package
$needsBuild = $Rebuild -or -not $installed -or -not $saved -or $saved.device -ne $DeviceId -or $saved.hash -ne $fingerprint
if ($needsBuild) {
    if (-not (Test-Path $flutter)) { throw "Flutter was not found at $flutter." }
    Push-Location $appRoot
    try {
        & $flutter build apk --debug --dart-define=API_URL=http://127.0.0.1:8080/api/v1
        if ($LASTEXITCODE -ne 0) { throw 'Flutter build failed; the installed app was not changed.' }
        & $adb -s $DeviceId install -r "$appRoot\build\app\outputs\flutter-apk\app-debug.apk"
        if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
        @{ device = $DeviceId; hash = $fingerprint } | ConvertTo-Json | Set-Content $marker
    } finally { Pop-Location }
} else { Write-Host 'No mobile source changes: reusing the installed app.' }
& $adb -s $DeviceId shell am start -W -n "$package/.MainActivity"
if ($LASTEXITCODE -ne 0) { throw 'Could not launch the delivery app.' }
