# kopy 설치 파일(dist\kopy-setup.exe)을 만듭니다.
# 필요: python -m pip install pyinstaller
# 실행: powershell -ExecutionPolicy Bypass -File 설치파일만들기\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
Set-Location $root
$work = Join-Path $env:TEMP "kopy-build"
New-Item -ItemType Directory -Force $work | Out-Null
$env:KOPY_WORK = $work
$icon = "$root\logo\kopy.ico"

# 0) 표준 라이브러리 전체 목록 (json, tkinter, sqlite3 ... 모두 쓸 수 있게)
python "$PSScriptRoot\stdlib_list.py" "$work\kopy_stdlib.py"

# 1) build\kopy\ 에 kopy.exe + "kopy 편집기.exe" + _internal
python -m PyInstaller --noconfirm --distpath "$root\build" --workpath $work "$PSScriptRoot\kopy.spec"

# 2) dist\kopy-setup.exe (kopy 폴더 + 예제를 담은 설치 프로그램)
python -m PyInstaller --noconfirm --onefile --windowed --name kopy-setup --icon $icon `
    --add-data "$root\build\kopy;kopy" `
    --add-data "$root\예제;예제" `
    --distpath "$root\dist" --workpath $work --specpath $work "$PSScriptRoot\installer.py"

Write-Host "완료: dist\kopy-setup.exe"
