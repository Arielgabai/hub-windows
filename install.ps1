# install.ps1 — lance l'installation du hub (install.py) avec le Python du poste.
# Usage : clic droit > « Exécuter avec PowerShell », ou dans un terminal :
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 [--terminal wt] [--dry-run] ...
# Les arguments sont transmis tels quels à install.py (python install.py --help pour la liste).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = $null
foreach ($cand in @('py', 'python', 'python3')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $py = $cmd.Source; break }
}
if (-not $py) {
    Write-Host 'Python 3.10+ est nécessaire. Installe-le avec :' -ForegroundColor Yellow
    Write-Host '  winget install Python.Python.3.12'
    Write-Host 'puis rouvre ce terminal et relance install.ps1.'
    exit 1
}
foreach ($tool in @('git', 'claude')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "Attention : '$tool' est introuvable dans le PATH (voir README, Prérequis)." -ForegroundColor Yellow
    }
}
if ((Split-Path -Leaf $py) -eq 'py.exe') {
    & $py -3 "$here\install.py" @args
} else {
    & $py "$here\install.py" @args
}
exit $LASTEXITCODE
