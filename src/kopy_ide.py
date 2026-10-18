"""kopy 편집기 — kopy 코드를 쓰고 바로 실행하는 프로그램 (파이썬의 IDLE 같은 것).

    kopy-ide.exe [파일.kopy]
    python kopy_ide.py [파일.kopy]
"""

import codecs
import ctypes
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

import kopy

설치판 = getattr(sys, "frozen", False)
여기 = os.path.dirname(sys.executable if 설치판 else os.path.abspath(__file__))
자료폴더 = getattr(sys, "_MEIPASS", 여기)
아이콘 = os.path.join(자료폴더, "kopy.ico") if 설치판 else os.path.join(여기, "..", "logo", "kopy.ico")
예제폴더 = os.path.join(여기, "예제") if 설치판 else os.path.join(여기, "..", "예제")

새파일내용 = '# 여기에 kopy 코드를 쓰고 F5 를 누르면 실행돼요\n\n출력("안녕, kopy!")\n'

색 = {
    "배경": "#1e1e1e", "글자": "#d4d4d4", "선택": "#264f78", "커서": "#aeafad",
    "줄번호": "#6e7681", "줄번호배경": "#181818", "도구배경": "#252526", "도구글자": "#cccccc",
    "kw": "#c586c0", "bi": "#dcdcaa", "str": "#ce9178", "com": "#6a9955", "num": "#b5cea8",
    "출력배경": "#141414", "오류": "#f48771", "안내": "#4ec9b0", "입력": "#9cdcfe",
}


def 단어패턴(목록):
    return r"(?<!\w)(?:" + "|".join(sorted(map(re.escape, 목록), key=len, reverse=True)) + r")(?!\w)"


# 앞에서부터 처음 맞는 것이 이김 → 문자열·주석 안의 키워드는 색칠 안 됨
강조규칙 = re.compile("|".join([
    r"(?P<str>[fFrRbB]{0,2}(?:\"\"\"[\s\S]*?(?:\"\"\"|$)|'''[\s\S]*?(?:'''|$)|\"[^\"\n]*\"?|'[^'\n]*'?))",
    r"(?P<com>#[^\n]*)",
    r"(?P<kw>" + 단어패턴(list(kopy.키워드) + ["if", "elif", "else", "for", "in", "while", "def", "return",
                                            "class", "import", "from", "as", "True", "False", "None",
                                            "and", "or", "not", "try", "except", "finally", "with"]) + ")",
    r"(?P<bi>" + 단어패턴(list(kopy.내장)) + ")",
    r"(?P<num>(?<!\w)\d+(?:\.\d+)?(?!\w))",
]))


def 실행명령(파일):
    if 설치판:
        return [os.path.join(여기, "kopy.exe"), 파일]
    return [sys.executable, os.path.join(여기, "kopy.py"), 파일]


class 편집기:
    def __init__(self, 창, 파일=None):
        self.창 = 창
        self.파일 = None
        self.프로세스 = None
        self.큐 = queue.Queue()
        self.강조예약 = None

        가족 = set(tkfont.families())
        글꼴이름 = next((f for f in ("D2Coding", "Cascadia Mono", "Consolas") if f in 가족), "Courier New")
        self.글꼴 = tkfont.Font(family=글꼴이름, size=12)
        self.작은글꼴 = tkfont.Font(family="맑은 고딕", size=10)

        창.geometry("980x720")
        창.configure(bg=색["도구배경"])
        try:
            창.iconbitmap(아이콘)
        except tk.TclError:
            pass

        self._메뉴()
        self._도구막대()
        self._화면()
        self._단축키()

        창.protocol("WM_DELETE_WINDOW", self.끝내기)
        if 파일 and os.path.exists(파일):
            self.열기(파일)
        else:
            self.새로(묻기=False)
        self.창.after(30, self._큐처리)

    # ── 화면 구성 ────────────────────────────────────────

    def _메뉴(self):
        메뉴 = tk.Menu(self.창)
        파일 = tk.Menu(메뉴, tearoff=0)
        파일.add_command(label="새 파일", accelerator="Ctrl+N", command=self.새로)
        파일.add_command(label="열기...", accelerator="Ctrl+O", command=self.열기)
        파일.add_command(label="예제 열기...", command=self.예제열기)
        파일.add_separator()
        파일.add_command(label="저장", accelerator="Ctrl+S", command=self.저장)
        파일.add_command(label="다른 이름으로 저장...", accelerator="Ctrl+Shift+S", command=self.다른이름저장)
        파일.add_separator()
        파일.add_command(label="끝내기", command=self.끝내기)
        메뉴.add_cascade(label="파일", menu=파일)

        실행 = tk.Menu(메뉴, tearoff=0)
        실행.add_command(label="실행", accelerator="F5", command=self.실행)
        실행.add_command(label="중지", accelerator="Ctrl+F2", command=self.중지)
        실행.add_command(label="파이썬으로 바뀐 코드 보기", command=self.변환보기)
        메뉴.add_cascade(label="실행", menu=실행)

        도움 = tk.Menu(메뉴, tearoff=0)
        도움.add_command(label="키워드 표", command=self.키워드표)
        도움.add_command(label="kopy 정보", command=lambda: messagebox.showinfo(
            "kopy 정보", f"kopy {kopy.버전}\n한국어로 쓰는 파이썬"))
        메뉴.add_cascade(label="도움말", menu=도움)
        self.창.config(menu=메뉴)

    def _도구막대(self):
        막대 = tk.Frame(self.창, bg=색["도구배경"], padx=8, pady=6)
        막대.pack(fill="x")

        def 단추(글, 명령, 강조=False):
            b = tk.Button(막대, text=글, command=명령, relief="flat", bd=0, padx=12, pady=4,
                          font=self.작은글꼴, cursor="hand2",
                          bg="#0e639c" if 강조 else "#3a3d41", fg="white",
                          activebackground="#1177bb" if 강조 else "#45494e", activeforeground="white")
            b.pack(side="left", padx=(0, 6))
            return b

        단추("새 파일", self.새로)
        단추("열기", self.열기)
        단추("저장", self.저장)
        self.실행단추 = 단추("▶ 실행 (F5)", self.실행, 강조=True)
        self.중지단추 = 단추("■ 중지", self.중지)
        self.상태 = tk.Label(막대, text="", bg=색["도구배경"], fg=색["도구글자"], font=self.작은글꼴)
        self.상태.pack(side="right")

    def _화면(self):
        나눔 = tk.PanedWindow(self.창, orient="vertical", sashwidth=6, bg=색["도구배경"], bd=0)
        나눔.pack(fill="both", expand=True)

        # 편집 영역
        위 = tk.Frame(나눔, bg=색["배경"])
        self.줄번호 = tk.Canvas(위, width=48, bg=색["줄번호배경"], highlightthickness=0)
        self.줄번호.pack(side="left", fill="y")
        스크롤 = tk.Scrollbar(위, orient="vertical")
        스크롤.pack(side="right", fill="y")
        self.글 = tk.Text(위, font=self.글꼴, undo=True, autoseparators=True, maxundo=-1, wrap="none",
                         bg=색["배경"], fg=색["글자"], insertbackground=색["커서"], selectbackground=색["선택"],
                         relief="flat", bd=0, padx=8, pady=6, tabs=self.글꼴.measure("    "))
        self.글.pack(side="left", fill="both", expand=True)
        self.글.config(yscrollcommand=lambda *a: (스크롤.set(*a), self._줄번호그리기()))
        스크롤.config(command=self.글.yview)
        for 이름 in ("kw", "bi", "str", "com", "num"):
            self.글.tag_configure(이름, foreground=색[이름])
        나눔.add(위, stretch="always", minsize=150)

        # 출력 영역
        아래 = tk.Frame(나눔, bg=색["출력배경"])
        tk.Label(아래, text="  출력", anchor="w", bg=색["도구배경"], fg=색["도구글자"],
                 font=self.작은글꼴).pack(fill="x")
        self.출력 = tk.Text(아래, font=self.글꼴, height=10, wrap="char", bg=색["출력배경"], fg=색["글자"],
                           relief="flat", bd=0, padx=8, pady=6, state="disabled",
                           insertbackground=색["커서"], selectbackground=색["선택"])
        self.출력.tag_configure("오류", foreground=색["오류"])
        self.출력.tag_configure("안내", foreground=색["안내"])
        self.출력.tag_configure("입력", foreground=색["입력"])
        self.출력.pack(fill="both", expand=True)

        입력줄 = tk.Frame(아래, bg=색["출력배경"])
        입력줄.pack(fill="x")
        tk.Label(입력줄, text=" 입력 ▶", bg=색["출력배경"], fg=색["입력"], font=self.작은글꼴).pack(side="left")
        self.입력칸 = tk.Entry(입력줄, font=self.글꼴, bg="#252526", fg=색["글자"], relief="flat",
                             insertbackground=색["커서"])
        self.입력칸.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.입력칸.bind("<Return>", self._입력보내기)
        나눔.add(아래, minsize=100)
        self.창.after(50, lambda: 나눔.sash_place(0, 0, 470))

    def _단축키(self):
        g, c = self.글, self.창
        c.bind("<F5>", lambda e: self.실행())
        c.bind("<Control-F2>", lambda e: self.중지())
        c.bind("<Control-n>", lambda e: self.새로())
        c.bind("<Control-o>", lambda e: (self.열기(), "break")[1])
        c.bind("<Control-s>", lambda e: self.저장())
        c.bind("<Control-S>", lambda e: self.다른이름저장())
        g.bind("<Tab>", self._탭)
        g.bind("<Shift-Tab>", self._내어쓰기)
        g.bind("<Return>", self._엔터)
        g.bind("<BackSpace>", self._지우기)
        g.bind("<<Modified>>", self._바뀜)
        g.bind("<KeyRelease>", self._바뀜)
        g.bind("<<Paste>>", lambda e: self.창.after(10, self._바뀜))
        g.bind("<Configure>", lambda e: self._줄번호그리기())

    # ── 편집 도우미 ──────────────────────────────────────

    def _탭(self, e):
        if self.글.tag_ranges("sel"):
            시작 = int(self.글.index("sel.first").split(".")[0])
            끝 = int(self.글.index("sel.last").split(".")[0])
            for 줄 in range(시작, 끝 + 1):
                self.글.insert(f"{줄}.0", "    ")
        else:
            self.글.insert("insert", "    ")
        return "break"

    def _내어쓰기(self, e):
        if self.글.tag_ranges("sel"):
            줄들 = range(int(self.글.index("sel.first").split(".")[0]), int(self.글.index("sel.last").split(".")[0]) + 1)
        else:
            줄들 = [int(self.글.index("insert").split(".")[0])]
        for 줄 in 줄들:
            앞 = self.글.get(f"{줄}.0", f"{줄}.4")
            칸 = len(앞) - len(앞.lstrip(" "))
            if 칸:
                self.글.delete(f"{줄}.0", f"{줄}.{칸}")
        return "break"

    def _엔터(self, e):
        줄 = self.글.get("insert linestart", "insert")
        들여 = len(줄) - len(줄.lstrip(" "))
        if 줄.split("#")[0].rstrip().endswith(":"):
            들여 += 4
        elif 줄.strip().split(" ")[0] in ("반환", "중단", "계속", "통과", "발생"):
            들여 = max(0, 들여 - 4)
        self.글.insert("insert", "\n" + " " * 들여)
        self.글.see("insert")
        return "break"

    def _지우기(self, e):
        if self.글.tag_ranges("sel"):
            return None
        앞 = self.글.get("insert linestart", "insert")
        if 앞 and not 앞.strip(" ") and len(앞) % 4 == 0:
            self.글.delete("insert-4c", "insert")
            return "break"
        return None

    def _바뀜(self, e=None):
        self._제목()
        self._줄번호그리기()
        if self.강조예약:
            self.창.after_cancel(self.강조예약)
        self.강조예약 = self.창.after(120, self._강조)

    def _강조(self):
        self.강조예약 = None
        글 = self.글.get("1.0", "end-1c")
        for 이름 in ("kw", "bi", "str", "com", "num"):
            self.글.tag_remove(이름, "1.0", "end")
        for m in 강조규칙.finditer(글):
            self.글.tag_add(m.lastgroup, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def _줄번호그리기(self):
        c = self.줄번호
        c.delete("all")
        i = self.글.index("@0,0")
        while True:
            d = self.글.dlineinfo(i)
            if d is None:
                break
            c.create_text(40, d[1] + 6, anchor="ne", text=i.split(".")[0], fill=색["줄번호"], font=self.글꼴)
            다음 = self.글.index(f"{i}+1line")
            if 다음 == i:
                break
            i = 다음

    def _제목(self):
        이름 = os.path.basename(self.파일) if self.파일 else "제목 없음"
        표시 = "● " if self.글.edit_modified() else ""
        self.창.title(f"{표시}{이름} — kopy 편집기")

    # ── 파일 ────────────────────────────────────────────

    def _내용설정(self, 내용):
        self.글.delete("1.0", "end")
        self.글.insert("1.0", 내용)
        self.글.edit_reset()
        self.글.edit_modified(False)
        self._강조()
        self._제목()
        self._줄번호그리기()

    def _버려도되나(self):
        if not self.글.edit_modified():
            return True
        답 = messagebox.askyesnocancel("저장", "바뀐 내용을 저장할까요?")
        if 답 is None:
            return False
        return self.저장() if 답 else True

    def 새로(self, 묻기=True):
        if 묻기 and not self._버려도되나():
            return
        self.파일 = None
        self._내용설정(새파일내용)
        self.글.mark_set("insert", "end")

    def 열기(self, 파일=None, 폴더=None):
        if not 파일:
            if not self._버려도되나():
                return
            파일 = filedialog.askopenfilename(
                initialdir=폴더, filetypes=[("kopy 파일", "*.kopy"), ("모든 파일", "*.*")])
            if not 파일:
                return
        with open(파일, encoding="utf-8-sig") as f:
            내용 = f.read()
        self.파일 = os.path.abspath(파일)
        self._내용설정(내용)
        self.글.mark_set("insert", "1.0")

    def 예제열기(self):
        self.열기(폴더=os.path.abspath(예제폴더))

    def 저장(self):
        if not self.파일:
            return self.다른이름저장()
        with open(self.파일, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.글.get("1.0", "end-1c"))
        self.글.edit_modified(False)
        self._제목()
        self.상태.config(text=f"저장함: {os.path.basename(self.파일)}")
        return True

    def 다른이름저장(self):
        파일 = filedialog.asksaveasfilename(defaultextension=".kopy",
                                          filetypes=[("kopy 파일", "*.kopy"), ("모든 파일", "*.*")])
        if not 파일:
            return False
        self.파일 = 파일
        return self.저장()

    def 끝내기(self):
        if self._버려도되나():
            self.중지()
            self.창.destroy()

    # ── 실행 ────────────────────────────────────────────

    def _출력쓰기(self, 글, 태그=None):
        self.출력.config(state="normal")
        self.출력.insert("end", 글, 태그)
        self.출력.see("end")
        self.출력.config(state="disabled")

    def 실행(self):
        if self.글.edit_modified() or not self.파일:
            if not self.저장():
                return
        self.중지()
        self.출력.config(state="normal")
        self.출력.delete("1.0", "end")
        self.출력.config(state="disabled")
        self._출력쓰기(f"▶ {os.path.basename(self.파일)} 실행\n", "안내")

        환경 = dict(os.environ, KOPY_UNBUFFERED="1")
        try:
            self.프로세스 = subprocess.Popen(
                실행명령(self.파일), cwd=os.path.dirname(self.파일), env=환경,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as e:
            self._출력쓰기(f"실행할 수 없어요: {e}\n", "오류")
            return
        프로세스 = self.프로세스
        for 흐름, 태그 in ((프로세스.stdout, None), (프로세스.stderr, "오류")):
            threading.Thread(target=self._읽기, args=(프로세스, 흐름, 태그), daemon=True).start()
        threading.Thread(target=self._기다리기, args=(프로세스,), daemon=True).start()
        self.상태.config(text="실행 중...")
        self.입력칸.focus_set()

    def _읽기(self, 프로세스, 흐름, 태그):
        해독 = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            조각 = 흐름.read1(4096)
            if not 조각:
                break
            self.큐.put((프로세스, 해독.decode(조각).replace("\r\n", "\n"), 태그))

    def _기다리기(self, 프로세스):
        코드 = 프로세스.wait()
        self.큐.put((프로세스, None, 코드))

    def _큐처리(self):
        try:
            while True:
                프로세스, 글, 태그 = self.큐.get_nowait()
                if 글 is None:
                    if 프로세스 is self.프로세스:
                        self.창.after(100, self._끝남, 프로세스, 태그)
                else:
                    self._출력쓰기(글, 태그)
        except queue.Empty:
            pass
        self.창.after(30, self._큐처리)

    def _끝남(self, 프로세스, 코드):
        if 프로세스 is not self.프로세스:
            return
        self.프로세스 = None
        self._출력쓰기(f"\n■ 끝남 (종료 코드 {코드})\n", "안내")
        self.상태.config(text="")

    def 중지(self):
        if self.프로세스 and self.프로세스.poll() is None:
            self.프로세스.kill()
            self._출력쓰기("\n■ 중지함\n", "오류")
        self.프로세스 = None
        self.상태.config(text="")

    def _입력보내기(self, e):
        글 = self.입력칸.get()
        self.입력칸.delete(0, "end")
        if not (self.프로세스 and self.프로세스.poll() is None):
            self.상태.config(text="실행 중인 프로그램이 없어요")
            return
        self._출력쓰기(글 + "\n", "입력")
        try:
            self.프로세스.stdin.write((글 + "\n").encode("utf-8"))
            self.프로세스.stdin.flush()
        except OSError:
            pass

    # ── 도움말 ──────────────────────────────────────────

    def _글창(self, 제목, 내용):
        창 = tk.Toplevel(self.창)
        창.title(제목)
        창.geometry("560x600")
        t = tk.Text(창, font=self.글꼴, bg=색["배경"], fg=색["글자"], relief="flat", padx=12, pady=10)
        t.insert("1.0", 내용)
        for m in 강조규칙.finditer(내용):
            t.tag_add(m.lastgroup, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for 이름 in ("kw", "bi", "str", "com", "num"):
            t.tag_configure(이름, foreground=색[이름])
        t.config(state="disabled")
        t.pack(fill="both", expand=True)

    def 키워드표(self):
        줄들 = ["# 키워드"] + [f"{k:<10} {v}" for k, v in kopy.키워드.items()]
        줄들 += ["", "# 내장 함수·이름"] + [f"{k:<10} {v}" for k, v in kopy.내장.items()]
        줄들 += ["", "# 메서드 (점 뒤에 씀: 목록.추가(1))"] + [f".{k:<9} .{v}" for k, v in kopy.메서드.items()]
        self._글창("키워드 표", "\n".join(줄들))

    def 변환보기(self):
        self._글창("파이썬으로 바뀐 코드", kopy.번역(self.글.get("1.0", "end-1c")))


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 고해상도 화면에서 글자가 흐리지 않게
    except Exception:
        pass
    창 = tk.Tk()
    편집기(창, sys.argv[1] if len(sys.argv) > 1 else None)
    창.mainloop()


if __name__ == "__main__":
    main()
