"""빌드용: 파이썬 표준 라이브러리 전체를 import 하는 파일을 만듭니다.

PyInstaller 는 kopy.py 가 직접 쓰는 모듈만 넣기 때문에, 이 파일을 함께 분석시켜
kopy.exe 에서도 json, tkinter, sqlite3 등 모든 표준 모듈을 쓸 수 있게 합니다.

사용: python stdlib_list.py 출력파일.py
"""

import importlib
import pkgutil
import sys

# 설치판에 필요 없거나, import 만 해도 부작용이 있는 것
제외 = {"test", "idlelib", "turtledemo", "lib2to3", "ensurepip", "this", "antigravity",
        "__phello__", "_testcapi", "_testinternalcapi", "_testbuffer", "_testimportmultiple",
        "_testmultiphase", "_testsinglephase", "_xxtestfuzz", "xxlimited", "xxlimited_35"}


def 제외됨(이름):
    return any(이름 == e or 이름.startswith(e + ".") for e in 제외) or ".test" in 이름 or ".tests" in 이름


def 모든모듈():
    이름들 = set()
    for 최상위 in sorted(sys.stdlib_module_names):
        if 제외됨(최상위):
            continue
        try:
            모듈 = importlib.import_module(최상위)
        except Exception:
            continue  # 이 운영체제에 없는 모듈 (posix, curses 등)
        이름들.add(최상위)
        if hasattr(모듈, "__path__"):
            for 정보 in pkgutil.walk_packages(모듈.__path__, 최상위 + ".", onerror=lambda _: None):
                if not 제외됨(정보.name) and not 정보.name.endswith("__main__"):
                    이름들.add(정보.name)
    return sorted(이름들)


if __name__ == "__main__":
    목록 = 모든모듈()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write("# 자동 생성 — 직접 실행하지 않음\n")
        for 이름 in 목록:
            f.write(f"import {이름}\n")
    print(f"표준 모듈 {len(목록)}개")
