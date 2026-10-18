"""kopy 설치 프로그램 (kopy-setup.exe 로 빌드됨).

- %LOCALAPPDATA%\\Programs\\kopy 에 설치. 보이는 건 세 가지만:
    kopy.exe, kopy 편집기.exe, 예제 폴더 (나머지는 숨긴 _internal 폴더 안에)
- 사용자 PATH 에 추가 → 어디서든 `kopy` 명령어 사용
- .kopy 파일 연결 → 더블클릭하면 실행, 우클릭 → kopy 편집기로 편집
- 시작 메뉴·바탕 화면에 "kopy 편집기" 바로 가기
- 설정 > 앱 목록에 등록 → 거기서 제거 가능

관리자 권한 없이 현재 사용자에게만 설치됩니다.
`kopy-setup.exe --제거` 로 제거합니다.
"""

import ctypes
import os
import shutil
import subprocess
import sys
import winreg

버전 = "0.4.0"
설치폴더 = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "kopy")
제거키 = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\kopy"
편집기이름 = "kopy 편집기.exe"
분류이름 = "kopy.File"  # ProgID 는 영어로 — 한글이면 탐색기가 아이콘·종류를 못 읽음
옛분류이름 = "kopy.소스파일"  # 0.3.0 이하

MB_OK, MB_YESNO, MB_ICONINFO, MB_ICONQ, MB_ICONERR = 0x0, 0x4, 0x40, 0x20, 0x10
IDYES = 6


def 알림(내용, 종류=MB_OK | MB_ICONINFO):
    return ctypes.windll.user32.MessageBoxW(None, 내용, "kopy 설치", 종류)


def 설정변경알리기():
    # 탐색기에 파일 연결 변경 알림
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    # 다른 프로그램에 PATH 변경 알림
    결과 = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 5000, ctypes.byref(결과))


def 바로가기(만들기):
    """시작 메뉴와 바탕 화면에 'kopy 편집기' 바로 가기를 만들거나 지웁니다."""
    환경 = dict(os.environ, KOPY_IDE=os.path.join(설치폴더, 편집기이름), KOPY_DIR=설치폴더,
              KOPY_MAKE="1" if 만들기 else "")
    명령 = (
        "$s = New-Object -ComObject WScript.Shell; "
        "foreach ($d in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) { "
        "  $f = Join-Path $d 'kopy 편집기.lnk'; "
        "  if ($env:KOPY_MAKE) { $l = $s.CreateShortcut($f); $l.TargetPath = $env:KOPY_IDE; "
        "    $l.WorkingDirectory = [Environment]::GetFolderPath('MyDocuments'); "
        "    $l.IconLocation = $env:KOPY_IDE + ',0'; $l.Description = 'kopy 편집기'; $l.Save() } "
        "  elseif (Test-Path $f) { Remove-Item $f } }"
    )
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", 명령],
                   env=환경, creationflags=0x08000000, check=False)


def 경로_읽기():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as 키:
        try:
            값, 형 = winreg.QueryValueEx(키, "Path")
        except FileNotFoundError:
            값, 형 = "", winreg.REG_EXPAND_SZ
    return 값, 형


def 경로_쓰기(값, 형):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as 키:
        winreg.SetValueEx(키, "Path", 0, 형, 값)


def 값설정(경로, 이름, 값):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 경로) as 키:
        winreg.SetValueEx(키, 이름, 0, winreg.REG_SZ, 값)


def 키삭제(경로):
    """하위 키까지 모두 삭제."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 경로) as 키:
            while True:
                try:
                    하위 = winreg.EnumKey(키, 0)
                except OSError:
                    break
                키삭제(경로 + "\\" + 하위)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, 경로)
    except FileNotFoundError:
        pass


def 설치():
    if 알림(f"kopy {버전}을(를) 설치할까요?\n\n설치 위치: {설치폴더}\n\n"
            "• 어디서든 kopy 명령어 사용\n• .kopy 파일 더블클릭으로 실행", MB_YESNO | MB_ICONQ) != IDYES:
        return

    # 파일 복사
    os.makedirs(설치폴더, exist_ok=True)
    원본 = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "kopy")
    kopy경로 = os.path.join(설치폴더, "kopy.exe")
    # 예전 버전 파일 정리
    shutil.rmtree(os.path.join(설치폴더, "_internal"), ignore_errors=True)
    for 옛파일 in ("kopy-ide.exe", "uninstall.exe"):
        try:
            os.remove(os.path.join(설치폴더, 옛파일))
        except OSError:
            pass
    shutil.copytree(원본, 설치폴더, dirs_exist_ok=True)
    # 초보자가 헷갈리지 않게 실행에 필요한 내부 파일 폴더는 숨김
    내부폴더 = os.path.join(설치폴더, "_internal")
    ctypes.windll.kernel32.SetFileAttributesW(내부폴더, 0x2)
    제거프로그램 = os.path.join(내부폴더, "uninstall.exe")
    if os.path.abspath(sys.executable) != os.path.abspath(제거프로그램):
        shutil.copy2(sys.executable, 제거프로그램)
    예제폴더 = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "예제")
    if os.path.isdir(예제폴더):
        shutil.copytree(예제폴더, os.path.join(설치폴더, "예제"), dirs_exist_ok=True)

    # PATH 추가
    값, 형 = 경로_읽기()
    항목들 = [p for p in 값.split(";") if p]
    if not any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(설치폴더) for p in 항목들):
        경로_쓰기(";".join(항목들 + [설치폴더]), 형)

    # .kopy 파일 연결
    키삭제(rf"Software\Classes\{옛분류이름}")
    분류 = rf"Software\Classes\{분류이름}"
    값설정(r"Software\Classes\.kopy", "", 분류이름)
    값설정(r"Software\Classes\.kopy", "Content Type", "text/plain")
    값설정(r"Software\Classes\.kopy", "PerceivedType", "text")
    값설정(r"Software\Classes\.kopy\OpenWithProgids", 분류이름, "")
    값설정(분류, "", "kopy 소스 파일")
    값설정(분류 + r"\DefaultIcon", "", f'"{kopy경로}",0')
    값설정(분류 + r"\shell", "", "open")
    값설정(분류 + r"\shell\open", "", "kopy로 실행")
    값설정(분류 + r"\shell\open\command", "", f'"{kopy경로}" --더블클릭 "%1"')
    편집기경로 = os.path.join(설치폴더, 편집기이름)
    값설정(분류 + r"\shell\edit", "", "kopy 편집기로 편집")
    값설정(분류 + r"\shell\edit", "Icon", f'"{편집기경로}",0')
    값설정(분류 + r"\shell\edit\command", "", f'"{편집기경로}" "%1"')

    바로가기(만들기=True)

    # 앱 목록 등록
    값설정(제거키, "DisplayName", "kopy (한국어 파이썬)")
    값설정(제거키, "DisplayVersion", 버전)
    값설정(제거키, "Publisher", "kopy")
    값설정(제거키, "InstallLocation", 설치폴더)
    값설정(제거키, "DisplayIcon", kopy경로)
    값설정(제거키, "UninstallString", f'"{제거프로그램}" --제거')

    설정변경알리기()
    알림("설치 완료!\n\n• 시작 메뉴·바탕 화면의 'kopy 편집기'로 코드를 쓰고 실행할 수 있어요.\n"
         "• .kopy 파일을 더블클릭하면 실행, 우클릭 → 'kopy 편집기로 편집'.\n"
         "• 새로 연 터미널에서 kopy 명령어를 쓸 수 있어요.\n"
         f"• 예제: {os.path.join(설치폴더, '예제')}")


def 제거():
    if 알림("kopy를 제거할까요?", MB_YESNO | MB_ICONQ) != IDYES:
        return

    값, 형 = 경로_읽기()
    남길것 = [p for p in 값.split(";") if p and os.path.normcase(p.rstrip("\\")) != os.path.normcase(설치폴더)]
    경로_쓰기(";".join(남길것), 형)

    키삭제(rf"Software\Classes\{분류이름}")
    키삭제(rf"Software\Classes\{옛분류이름}")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.kopy") as 키:
            현재, _ = winreg.QueryValueEx(키, "")
        if 현재 in (분류이름, 옛분류이름):
            키삭제(r"Software\Classes\.kopy")
    except FileNotFoundError:
        pass
    키삭제(제거키)
    바로가기(만들기=False)
    설정변경알리기()

    # 실행 중인 uninstall.exe 는 스스로 못 지우므로, 끝난 뒤 지우도록 예약
    subprocess.Popen(
        f'cmd /c ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{설치폴더}"',
        creationflags=0x08000000,  # 창 없이
        cwd=os.environ["TEMP"],
    )
    알림("kopy를 제거했어요.")


if __name__ == "__main__":
    try:
        if "--제거" in sys.argv[1:]:
            제거()
        else:
            설치()
    except Exception as e:
        알림(f"오류가 났어요:\n{e}", MB_OK | MB_ICONERR)
        sys.exit(1)
