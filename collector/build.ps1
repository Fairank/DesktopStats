param([switch]$SelfTest)
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$dependencyRoot = Join-Path $projectRoot 'third_party\librehardwaremonitor\0.9.6'
$runtimeRoot = Join-Path $PSScriptRoot 'runtime'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw 'The .NET Framework 64-bit C# compiler is unavailable. No SDK or runtime will be installed automatically.'
}
$manifestPath = Join-Path $dependencyRoot 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.provider -ne 'LibreHardwareMonitor' -or $manifest.version -ne '0.9.6' -or
    $manifest.source_commit -ne '3d331e3370efb858411f19511373eff65a218701' -or $manifest.files.Count -ne 9) {
    throw 'Unexpected sensor-library manifest.'
}
$allowedDlls = @(
    'LibreHardwareMonitorLib.dll', 'DiskInfoToolkit.dll', 'BlackSharp.Core.dll',
    'RAMSPDToolkit-NDD.dll', 'HidSharp.dll', 'System.Memory.dll', 'System.Buffers.dll',
    'System.Numerics.Vectors.dll', 'System.Runtime.CompilerServices.Unsafe.dll'
)
foreach ($entry in @($manifest.files) + @($manifest.licenses)) {
    if ([IO.Path]::GetFileName($entry.name) -ne $entry.name) { throw 'Invalid manifest filename.' }
    if ($entry.name.EndsWith('.dll') -and $entry.name -notin $allowedDlls) { throw 'Unexpected DLL.' }
    $path = Join-Path $dependencyRoot $entry.name
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $entry.sha256) { throw "Dependency integrity failed: $($entry.name)" }
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$existingExecutables = @(Get-ChildItem -LiteralPath $runtimeRoot -File | Where-Object {
    ($_.Extension -eq '.dll' -and $_.Name -notin $allowedDlls) -or
    ($_.Extension -eq '.exe' -and $_.Name -ne 'DesktopStats.Collector.exe') -or
    $_.Extension -in @('.sys', '.inf', '.cat')
})
if ($existingExecutables.Count) { throw 'Unexpected executable/driver in collector runtime; inspect it before building.' }

# This is a local build with fixed, verified library files. There are no downloads
# and no downloaded executable is run. Referenced DLLs are metadata inputs to csc.
foreach ($entry in @($manifest.files) + @($manifest.licenses)) {
    Copy-Item -LiteralPath (Join-Path $dependencyRoot $entry.name) -Destination (Join-Path $runtimeRoot $entry.name) -Force
}
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $runtimeRoot 'library-manifest.json') -Force
Copy-Item -LiteralPath (Join-Path $dependencyRoot 'NOTICE.md') -Destination (Join-Path $runtimeRoot 'THIRD-PARTY-NOTICES.md') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'DesktopStats.Collector.exe.config') -Destination $runtimeRoot -Force
$target = Join-Path $runtimeRoot 'DesktopStats.Collector.exe'
$source = Join-Path $PSScriptRoot 'Program.cs'
& $compiler /nologo /target:exe /platform:x64 /optimize+ /checked+ /utf8output "/out:$target" "/reference:$(Join-Path $dependencyRoot 'LibreHardwareMonitorLib.dll')" /reference:System.Web.Extensions.dll $source
if ($LASTEXITCODE -ne 0) { throw "Collector compilation failed ($LASTEXITCODE)." }

$build = [ordered]@{
    schema = 1
    provider = 'LibreHardwareMonitor'
    provider_version = '0.9.6'
    upstream_commit = $manifest.source_commit
    compiler_version = (Get-Item -LiteralPath $compiler).VersionInfo.FileVersion
    target = '.NETFramework,Version=v4.7.2'
    architecture = 'x64'
    sources = @('Program.cs', 'build.ps1', 'DesktopStats.Collector.exe.config') | ForEach-Object {
        [ordered]@{ name = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $_) -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
    files = Get-ChildItem -LiteralPath $runtimeRoot -File | Where-Object { $_.Name -ne 'build-manifest.json' } | Sort-Object Name | ForEach-Object {
        [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
$build | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $runtimeRoot 'build-manifest.json') -Encoding UTF8
if ($SelfTest) {
    # This original executable's synthetic branch never constructs Computer or
    # invokes downloaded-library hardware APIs. Real probing is a separate step.
    & $target --self-test
    if ($LASTEXITCODE -ne 0) { throw "Collector synthetic self-test failed ($LASTEXITCODE)." }
}
Write-Host 'Collector build complete. No hardware probe was requested.'
