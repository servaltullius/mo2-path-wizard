$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

python -m pip install -U pip
python -m pip install -e .
python -m pip install pyinstaller

pyinstaller --noconfirm --clean --onefile --name "mo2-path-wizard" --paths ".\\src" ".\\src\\mo2_path_wizard\\__main__.py"
pyinstaller --noconfirm --clean --onefile --windowed --name "mo2-path-wizard-gui" --paths ".\\src" ".\\src\\mo2_path_wizard\\gui.py"

Write-Host "Build complete. See .\\dist\\"
