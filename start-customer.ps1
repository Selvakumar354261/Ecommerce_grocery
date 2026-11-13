param([string]$DeviceId,[switch]$Rebuild)
& "$PSScriptRoot\start-mobile.ps1" -AppDirectory customer-mobile-flutter -DeviceId $DeviceId -Rebuild:$Rebuild
