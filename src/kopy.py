"""kopy — 한국어로 쓰는 파이썬.

kopy 코드(.kopy)를 파이썬 코드로 바꿔서 실행합니다.

사용법은 파이썬과 같습니다 (kopy -h 참고):
    kopy 파일.kopy [인자...]   # 실행
    kopy -c "출력(1 + 2)"      # 명령 실행
    kopy -m 모듈               # 모듈 실행
    kopy                       # 대화형 모드
"""

import builtins
import code
import importlib.machinery
import importlib.util
import io
import linecache
import os
import platform
import re
import runpy
import sys
import tokenize
import traceback
import types

버전 = "0.4.0"

# 한국어 키워드 → 파이썬 키워드
키워드 = {
    "만약": "if",
    "아니면만약": "elif",
    "아니면": "else",
    "반복": "for",
    "안에": "in",
    "동안": "while",
    "중단": "break",
    "계속": "continue",
    "통과": "pass",
    "함수": "def",
    "반환": "return",
    "클래스": "class",
    "참": "True",
    "거짓": "False",
    "없음": "None",
    "그리고": "and",
    "또는": "or",
    "아님": "not",
    "이다": "is",
    "가져오기": "import",
    "부터": "from",
    "로서": "as",
    "시도": "try",
    "예외": "except",
    "마침내": "finally",
    "발생": "raise",
    "단언": "assert",
    "전역": "global",
    "비지역": "nonlocal",
    "람다": "lambda",
    "함께": "with",
    "양보": "yield",
    "삭제": "del",
    "비동기": "async",
    "대기": "await",
}

# 한국어 내장 함수/이름 → 파이썬 이름
내장 = {
    "출력": "print",
    "입력": "input",
    "범위": "range",
    "길이": "len",
    "정수": "int",
    "실수": "float",
    "문자열": "str",
    "논리": "bool",
    "목록": "list",
    "사전": "dict",
    "집합": "set",
    "튜플": "tuple",
    "합계": "sum",
    "최대": "max",
    "최소": "min",
    "정렬": "sorted",
    "뒤집기": "reversed",
    "절댓값": "abs",
    "반올림": "round",
    "거듭제곱": "pow",
    "자료형": "type",
    "열거": "enumerate",
    "묶기": "zip",
    "변환": "map",
    "거르기": "filter",
    "모두": "all",
    "하나라도": "any",
    "열기": "open",
    "자기": "self",
    "생성자": "__init__",
    "문자표현": "__str__",
    "__이름__": "__name__",
    # 예외
    "오류": "Exception",
    "값오류": "ValueError",
    "형오류": "TypeError",
    "인덱스오류": "IndexError",
    "키오류": "KeyError",
    "이름오류": "NameError",
    "영나누기오류": "ZeroDivisionError",
    "속성오류": "AttributeError",
    "파일없음오류": "FileNotFoundError",
    "모듈없음오류": "ModuleNotFoundError",
    "가져오기오류": "ImportError",
    "단언오류": "AssertionError",
    "재귀오류": "RecursionError",
    "실행오류": "RuntimeError",
    "미구현오류": "NotImplementedError",
    "넘침오류": "OverflowError",
    "운영체제오류": "OSError",
    "반복끝": "StopIteration",
    "문법오류": "SyntaxError",
    "들여쓰기오류": "IndentationError",
    "키보드중단": "KeyboardInterrupt",
    "시스템종료": "SystemExit",
}

# 리스트·문자열 메서드 (점 뒤에 올 때만 바뀜: 목록.추가(1))
메서드 = {
    "추가": "append",
    "확장": "extend",
    "삽입": "insert",
    "제거": "remove",
    "꺼내기": "pop",
    "비우기": "clear",
    "찾기": "index",
    "세기": "count",
    "정렬하기": "sort",
    "뒤집": "reverse",
    "복사": "copy",
    "키들": "keys",
    "값들": "values",
    "항목들": "items",
    "가져": "get",
    "나누기": "split",
    "합치기": "join",
    "바꾸기": "replace",
    "대문자": "upper",
    "소문자": "lower",
    "다듬기": "strip",
    "시작확인": "startswith",
    "끝확인": "endswith",
    "형식": "format",
}

이름표 = {**내장, **키워드}
역번역 = {v: k for k, v in {**내장, **키워드}.items()}


def 번역(소스: str) -> str:
    """kopy 소스 코드를 파이썬 소스 코드로 바꿉니다. 줄 번호는 그대로 유지됩니다."""
    줄들 = 소스.splitlines(keepends=True)
    바꿀것 = []  # (줄, 시작열, 끝열, 새글자)
    try:
        토큰들 = list(tokenize.generate_tokens(io.StringIO(소스).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError, UnicodeError):
        return 소스  # 아직 덜 쓴 코드(대화형 모드) — 그대로 넘김

    이전 = None
    건너뛰기 = False
    for i, 토큰 in enumerate(토큰들):
        if 건너뛰기:
            건너뛰기 = False
            이전 = 토큰
            continue
        if 토큰.type == tokenize.NAME:
            글자 = 토큰.string
            점뒤 = 이전 is not None and 이전.type == tokenize.OP and 이전.string == "."
            새것 = None
            if 점뒤:
                새것 = 메서드.get(글자) or 내장.get(글자)
            elif 글자 == "아니면" and i + 1 < len(토큰들) and 토큰들[i + 1].string == "만약":
                # "아니면 만약" 두 단어도 elif 로
                다음 = 토큰들[i + 1]
                바꿀것.append((토큰.start[0], 토큰.start[1], 다음.end[1], "elif"))
                건너뛰기 = True
            else:
                새것 = 이름표.get(글자)
            if 새것:
                바꿀것.append((토큰.start[0], 토큰.start[1], 토큰.end[1], 새것))
        if 토큰.type not in (tokenize.NL, tokenize.COMMENT):
            이전 = 토큰

    # 뒤에서부터 바꿔야 앞쪽 위치가 안 틀어짐
    for 줄, 시작, 끝, 새것 in sorted(바꿀것, reverse=True):
        원래 = 줄들[줄 - 1]
        줄들[줄 - 1] = 원래[:시작] + 새것 + 원래[끝:]
    return "".join(줄들)


# ── .kopy 모듈 가져오기 ───────────────────────────────────────────


class kopy로더(importlib.machinery.SourceFileLoader):
    """`가져오기 도구` 로 같은 폴더의 도구.kopy 를 불러옵니다."""

    def path_stats(self, path):
        raise OSError  # .pyc 캐시를 쓰지 않음 — 번역 규칙이 바뀌어도 항상 새로 번역

    def source_to_code(self, data, path, *, _optimize=-1):
        소스 = importlib.util.decode_source(data).lstrip("﻿")
        return compile(번역(소스), path, "exec", dont_inherit=True, optimize=_optimize)


class kopy찾기:
    """sys.path 의 폴더에서 이름.kopy (또는 이름/__init__.kopy) 를 찾습니다.

    파이썬이 스크립트 폴더의 .py 를 먼저 찾는 것처럼, .kopy 를 먼저 찾습니다.
    """

    @staticmethod
    def find_spec(이름, 경로=None, 대상=None):
        끝이름 = 이름.rpartition(".")[2]
        for 폴더 in (경로 if 경로 is not None else sys.path):
            if not isinstance(폴더, str):
                continue
            폴더 = 폴더 or os.getcwd()
            패키지 = os.path.join(폴더, 끝이름, "__init__.kopy")
            if os.path.isfile(패키지):
                return importlib.util.spec_from_file_location(
                    이름, 패키지, loader=kopy로더(이름, 패키지),
                    submodule_search_locations=[os.path.dirname(패키지)])
            파일 = os.path.join(폴더, 끝이름 + ".kopy")
            if os.path.isfile(파일):
                return importlib.util.spec_from_file_location(이름, 파일, loader=kopy로더(이름, 파일))
        return None


def 가져오기설치():
    """`가져오기 도구` 가 도구.kopy 도 찾을 수 있게 합니다."""
    if not any(isinstance(f, type) and f.__name__ == "kopy찾기" for f in sys.meta_path):
        sys.meta_path.insert(0, kopy찾기)


# 설치판(kopy.exe)에서 `kopy -m pip install ...` 으로 받은 패키지가 들어가는 곳
패키지폴더 = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "kopy", "site-packages")
설치판 = getattr(sys, "frozen", False)


# ── 한국어 오류 메시지 ────────────────────────────────────────────

오류메시지번역 = [
    (r"invalid syntax$", "잘못된 문법이에요"),
    (r"expected ':'$", "':' 가 필요해요"),
    (r"unexpected indent$", "예상하지 못한 들여쓰기예요"),
    (r"expected an indented block.*", "들여쓰기된 블록이 필요해요"),
    (r"unindent does not match any outer indentation level$", "들여쓰기 칸 수가 맞지 않아요"),
    (r"'(.+)' was never closed$", r"'\1' 를 닫지 않았어요"),
    (r"unterminated string literal.*", "문자열 따옴표를 닫지 않았어요"),
    (r"name '(.+)' is not defined.*", r"'\1' 이(가) 정의되지 않았어요"),
    (r"No module named '(.+)'$", r"'\1' 모듈을 찾을 수 없어요"),
    (r"division by zero$", "0으로 나눌 수 없어요"),
    (r"(?:float )?division by zero$", "0으로 나눌 수 없어요"),
    (r"list index out of range$", "목록 범위를 벗어난 위치예요"),
    (r"string index out of range$", "문자열 범위를 벗어난 위치예요"),
    (r"invalid literal for int\(\) with base 10: (.+)$", r"\1 은(는) 정수로 바꿀 수 없어요"),
    (r"could not convert string to float: (.+)$", r"\1 은(는) 실수로 바꿀 수 없어요"),
    (r"maximum recursion depth exceeded.*", "재귀 호출이 너무 깊어요"),
]


def 메시지번역(글: str) -> str:
    for 패턴, 바꿈 in 오류메시지번역:
        if re.match(패턴, 글):
            return re.sub(패턴, 바꿈, 글)
    return 글


def 내부틀(파일: str) -> bool:
    """오류 추적에서 숨길 kopy 내부 틀인지."""
    if 파일.endswith(".kopy"):
        return False
    return 파일.startswith("<frozen") or os.path.basename(파일) in ("kopy.py", "runpy.py", "code.py")


def 오류보고(오류: BaseException) -> None:
    """파이썬처럼 오류 추적을 보여주되, 한국어로."""
    이름 = 역번역.get(type(오류).__name__, type(오류).__name__)
    줄들 = []
    틀들 = [틀 for 틀 in traceback.extract_tb(오류.__traceback__) if not 내부틀(틀.filename)]
    if 틀들:
        줄들.append("오류 추적 (가장 최근 호출이 마지막):")
        for 틀 in 틀들:
            안에서 = "" if 틀.name == "<module>" else f", {역번역.get(틀.name, 틀.name)} 안에서"
            줄들.append(f'  파일 "{틀.filename}", {틀.lineno}번째 줄{안에서}')
            if 틀.line:
                줄들.append("    " + 틀.line.strip())

    if isinstance(오류, SyntaxError):
        if 오류.lineno:
            줄들.append(f'  파일 "{오류.filename}", {오류.lineno}번째 줄')
            원래줄 = linecache.getline(오류.filename or "", 오류.lineno) or 오류.text or ""
            if 원래줄.strip():
                줄들.append("    " + 원래줄.strip())
        메시지 = 메시지번역(오류.msg or "")
    else:
        메시지 = 메시지번역(str(오류))
    줄들.append(f"{이름}: {메시지}" if 메시지 else 이름)
    print("\n".join(줄들), file=sys.stderr)


# ── 실행 ──────────────────────────────────────────────────────────


def 주모듈만들기(파일이름=None) -> dict:
    """새 __main__ 모듈을 만들고 그 이름공간을 돌려줍니다."""
    모듈 = types.ModuleType("__main__")
    모듈.__builtins__ = builtins
    if 파일이름:
        모듈.__file__ = 파일이름
    sys.modules["__main__"] = 모듈
    return 모듈.__dict__


def 소스실행(소스: str, 파일이름: str, 이름공간: dict) -> None:
    소스 = 소스.lstrip("﻿")
    # 오류 추적에 한국어 원본 줄이 나오도록 등록
    linecache.cache[파일이름] = (len(소스), None, 소스.splitlines(keepends=True), 파일이름)
    exec(compile(번역(소스), 파일이름, "exec", dont_inherit=True), 이름공간)


def 안전실행(함수) -> int:
    """함수를 실행하고 파이썬과 같은 종료 코드를 돌려줍니다."""
    try:
        함수()
        return 0
    except SystemExit as e:
        if e.code is None:
            return 0
        if isinstance(e.code, int):
            return e.code
        print(e.code, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n키보드중단", file=sys.stderr)
        return 130
    except BaseException as e:
        오류보고(e)
        return 1


class 대화형(code.InteractiveConsole):
    def runsource(self, source, filename="<kopy>", symbol="single"):
        linecache.cache["<kopy>"] = (len(source), None, source.splitlines(keepends=True), "<kopy>")
        return super().runsource(번역(source), "<kopy>", symbol)

    def showsyntaxerror(self, filename=None, **kwargs):
        오류보고(sys.exc_info()[1])

    def showtraceback(self):
        오류보고(sys.exc_info()[1])


def 대화형시작(이름공간=None) -> int:
    sys.ps1, sys.ps2 = "코파이> ", "...... "
    배너 = (f"kopy {버전} (Python {platform.python_version()})\n"
          "도움말은 도움(), 끝내려면 종료() 또는 Ctrl+Z 후 Enter")
    try:
        대화형(이름공간 if 이름공간 is not None else 주모듈만들기()).interact(banner=배너, exitmsg="안녕히 가세요!")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    return 0


도움말 = """사용법: kopy [옵션] [-c 명령 | -m 모듈 | 파일 | -] [인자...]

  파일           .kopy 파일 실행 (뒤의 인자는 sys.argv 로 전달)
  -c 명령        명령 문자열 실행
  -m 모듈        모듈을 스크립트로 실행 (.kopy 모듈, 파이썬 모듈 모두)
                 예) kopy -m pip install requests
  -              표준 입력에서 프로그램 읽기
  -i             실행한 뒤 대화형 모드로 들어가기
  -V, --version  버전 보기
  -h, --help     이 도움말 보기
  --변환 파일    파이썬으로 바뀐 코드 보기
  (인자 없음)    대화형 모드"""


def main(인자들) -> int:
    즉시출력 = bool(os.environ.get("KOPY_UNBUFFERED"))  # 편집기에서 실행할 때: 출력을 바로바로 보내기
    for 스트림 in (sys.stdout, sys.stderr):
        try:
            스트림.reconfigure(encoding="utf-8", write_through=즉시출력)
        except AttributeError:
            pass
    if 즉시출력:
        _원래출력 = builtins.print

        def 즉시print(*a, **k):
            _원래출력(*a, **k)
            (k.get("file") or sys.stdout).flush()
        builtins.print = 즉시print
    try:
        sys.stdin.reconfigure(encoding="utf-8-sig", errors="replace")
    except AttributeError:
        pass

    가져오기설치()
    if 설치판:
        sys.path.append(패키지폴더)
    if not hasattr(builtins, "exit"):  # 설치판에는 exit/quit 가 없음
        builtins.exit = builtins.quit = sys.exit
    builtins.종료 = builtins.exit
    builtins.도움 = getattr(builtins, "help", None) or (lambda *a: print("도움말을 쓸 수 없어요"))

    대화형으로 = False
    while 인자들 and 인자들[0] == "-i":
        대화형으로 = True
        인자들 = 인자들[1:]

    if not 인자들:
        return 대화형시작()

    첫째, 나머지 = 인자들[0], 인자들[1:]

    if 첫째 in ("-h", "--help", "/?"):
        print(도움말)
        return 0

    if 첫째 in ("-V", "--version"):
        print(f"kopy {버전} (Python {platform.python_version()})")
        return 0

    if 첫째 in ("--변환", "--python", "-p"):
        if not 나머지:
            print("사용법: kopy --변환 파일.kopy", file=sys.stderr)
            return 2
        with open(나머지[0], encoding="utf-8-sig") as f:
            print(번역(f.read()), end="")
        return 0

    if 첫째 == "-c":
        if not 나머지:
            print("-c 뒤에 실행할 명령이 필요해요", file=sys.stderr)
            return 2
        sys.argv = ["-c"] + 나머지[1:]
        sys.path.insert(0, "")
        이름공간 = 주모듈만들기()
        결과 = 안전실행(lambda: 소스실행(나머지[0], "<string>", 이름공간))

    elif 첫째 == "-m":
        if not 나머지:
            print("-m 뒤에 모듈 이름이 필요해요", file=sys.stderr)
            return 2
        모듈, 모듈인자 = 나머지[0], 나머지[1:]
        sys.path.insert(0, os.getcwd())
        if 설치판 and 모듈 == "pip" and 모듈인자[:1] == ["install"] and not any(
                a.startswith(("--target", "-t", "--prefix", "--root", "--user")) for a in 모듈인자):
            os.makedirs(패키지폴더, exist_ok=True)
            모듈인자 = ["install", "--target", 패키지폴더, "--upgrade"] + 모듈인자[1:]
        if 설치판 and 모듈 == "pip":
            try:  # 설치판 안의 pip 가 자기 리소스 파일을 찾을 수 있게
                from pip._vendor import distlib
                from pip._vendor.distlib import resources
                resources.register_finder(distlib.__loader__, resources.ResourceFinder)
            except Exception:
                pass
        try:
            있음 = importlib.util.find_spec(모듈) is not None
        except (ImportError, ValueError):
            있음 = False
        if not 있음:
            print(f"모듈없음오류: '{모듈}' 모듈을 찾을 수 없어요", file=sys.stderr)
            return 1
        sys.argv = [모듈] + 모듈인자
        결과 = 안전실행(lambda: runpy._run_module_as_main(모듈, alter_argv=True))
        이름공간 = sys.modules["__main__"].__dict__

    elif 첫째 == "-":
        sys.argv = ["-"] + 나머지
        sys.path.insert(0, "")
        이름공간 = 주모듈만들기()
        소스 = sys.stdin.read()
        결과 = 안전실행(lambda: 소스실행(소스, "<stdin>", 이름공간))

    elif 첫째.startswith("-"):
        print(f"알 수 없는 옵션: {첫째}\n", file=sys.stderr)
        print(도움말, file=sys.stderr)
        return 2

    else:
        파일이름 = 첫째
        try:
            with open(파일이름, encoding="utf-8-sig") as f:
                소스 = f.read()
        except FileNotFoundError:
            print(f"파일을 찾을 수 없어요: {파일이름}", file=sys.stderr)
            return 2
        sys.argv = 인자들
        sys.path.insert(0, os.path.dirname(os.path.abspath(파일이름)))
        이름공간 = 주모듈만들기(파일이름)
        결과 = 안전실행(lambda: 소스실행(소스, 파일이름, 이름공간))

    if 대화형으로:
        return 대화형시작(이름공간)
    return 결과


def cli():
    """`kopy` 명령어 진입점."""
    인자들 = sys.argv[1:]
    더블클릭 = "--더블클릭" in 인자들  # 파일을 더블클릭해서 열었을 때: 창이 바로 닫히지 않게
    if 더블클릭:
        인자들.remove("--더블클릭")
    결과 = main(인자들)
    if 더블클릭:
        try:
            input("\n[끝내려면 Enter를 누르세요]")
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(결과)


if __name__ == "__main__":
    cli()
