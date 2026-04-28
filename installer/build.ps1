$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --name AIConstructionDrawing --windowed --paths src --add-data "src\sketch_assistant\resources;sketch_assistant\resources" src\sketch_assistant\__main__.py

$InnoSetupPaths = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$InnoSetup = $InnoSetupPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($InnoSetup) {
    Write-Host "Using Inno Setup: $InnoSetup"
    & $InnoSetup installer\setup.iss
} else {
    Write-Host "Inno Setup not found. PyInstaller output is ready at dist\AIConstructionDrawing."
    Write-Host "Install Inno Setup 6 to build AIConstructionDrawingSetup.exe."
}
