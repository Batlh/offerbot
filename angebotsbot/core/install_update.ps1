param([Parameter(Mandatory=$true)][int]$AppPid, [switch]$Restart)
$ErrorActionPreference = 'Stop'
$stage = (Get-Item -LiteralPath $PSScriptRoot).FullName
$root = Split-Path -Parent $stage
$package = Join-Path $stage 'AngebotsBot'
$backup = Join-Path $stage 'vorher'
$exe = Join-Path $root 'AngebotsBot.exe'
if ((Split-Path -Leaf $stage) -notmatch '^\.offerbot-update-[A-Za-z0-9_-]+$' -or
    !(Test-Path -LiteralPath $exe -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $package 'AngebotsBot.exe') -PathType Leaf)) {
    throw 'Update-Ordner konnte nicht bestaetigt werden.'
}
$old = @()
$new = @()
$guard = $null
try {
    $parent = Get-Process -Id $AppPid -ErrorAction SilentlyContinue
    if ($parent -and !$parent.WaitForExit(120000)) { throw 'Programm ist noch geoeffnet.' }
    $guard = [IO.File]::Open((Join-Path $root '.offerbot-update.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    if (Get-Process -Name AngebotsBot -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }) {
        throw 'Eine weitere Instanz ist noch geoeffnet.'
    }
    $expected = Get-Content -LiteralPath (Join-Path $stage 'installiert.sha256') -Raw
    $hash = [System.Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($exe)
    try { $actual = [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $hash.Dispose() }
    if ($actual -ne $expected.Trim()) {
        throw 'Die installierte Version hat sich seit dem Download geaendert.'
    }
    New-Item -ItemType Directory -Path $backup | Out-Null
    foreach ($name in @('_internal','README.md','CHANGELOG.md','AngebotsBot.exe')) {
        $source = Join-Path $package $name
        if (!(Test-Path -LiteralPath $source)) { continue }
        $dest = Join-Path $root $name
        if (Test-Path -LiteralPath $dest) {
            Move-Item -LiteralPath $dest -Destination (Join-Path $backup $name)
            $old += $name
        }
        Move-Item -LiteralPath $source -Destination $dest
        $new += $name
    }
} catch {
    $failure = $_.Exception.Message
    foreach ($name in $new) {
        Move-Item -LiteralPath (Join-Path $root $name) -Destination (Join-Path $package $name)
    }
    foreach ($name in $old) {
        Move-Item -LiteralPath (Join-Path $backup $name) -Destination (Join-Path $root $name)
    }
    Set-Content -LiteralPath (Join-Path $stage 'update-error.txt') -Value $failure -Encoding UTF8
    exit 1
} finally {
    if ($guard) { $guard.Dispose() }
}
if ($Restart) { Start-Process -FilePath $exe -WorkingDirectory $root }
# Nur das vom Updater angelegte, unmittelbar unter dem Programmordner liegende Verzeichnis.
if ((Split-Path -Parent (Resolve-Path -LiteralPath $stage).Path) -eq $root -and
    (Split-Path -Leaf $stage) -match '^\.offerbot-update-[A-Za-z0-9_-]+$') {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
