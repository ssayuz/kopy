# PyInstaller 설정: kopy.exe(콘솔) 와 "kopy 편집기.exe"(창)를 한 폴더에 만듭니다.
# build.ps1 이 실행합니다. KOPY_WORK 폴더에 kopy_stdlib.py (표준 라이브러리 목록)가 있어야 합니다.
import os

from PyInstaller.utils.hooks import collect_all

루트 = os.path.dirname(SPECPATH)
소스 = os.path.join(루트, "src")
작업 = os.environ["KOPY_WORK"]
아이콘 = os.path.join(루트, "logo", "kopy.ico")

pip자료, pip바이너리, pip모듈 = collect_all("pip")
a = Analysis(
    [os.path.join(소스, "kopy.py")],
    pathex=[소스, 작업],
    hiddenimports=["kopy_stdlib"] + pip모듈,
    datas=pip자료,
    binaries=pip바이너리,
)
b = Analysis(
    [os.path.join(소스, "kopy_ide.py")],
    pathex=[소스],
    datas=[(아이콘, ".")],
)

kopy_exe = EXE(
    PYZ(a.pure), a.scripts, [],
    exclude_binaries=True, name="kopy", icon=아이콘, console=True,
)
ide_exe = EXE(
    PYZ(b.pure), b.scripts, [],
    exclude_binaries=True, name="kopy 편집기", icon=아이콘, console=False,
)
COLLECT(
    kopy_exe, a.binaries, a.datas,
    ide_exe, b.binaries, b.datas,
    name="kopy",
)
