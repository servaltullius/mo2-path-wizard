from __future__ import annotations

import json
import threading
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mo2_path_wizard.discovery import discover_from_root
from mo2_path_wizard.patcher import (
    CustomExecutableEntry,
    PatchOptions,
    PatchReport,
    inspect_custom_executables,
    patch_modorganizer_ini,
)


@dataclass(frozen=True)
class _PreviewContext:
    ini_path: Path | None
    instance_root: Path | None
    game_path: Path | None
    tool_root: Path | None
    executables: tuple[CustomExecutableEntry, ...]
    behavior_engine_auto_detect: bool = True


def _display_path(path: Path | None) -> str:
    if path is None:
        return "(감지 안 됨)"
    return str(path).replace("\\", "/")


def _display_ini_value(value: str) -> str:
    return value.replace("\\\\", "\\").replace("\\", "/")


def _entry_text(entry: CustomExecutableEntry) -> str:
    return " ".join((entry.title, entry.binary, entry.working_directory)).lower()


def _format_behavior_engine_detection(context: _PreviewContext) -> str:
    lines = ["[Pandora/Nemesis 자동 판단]"]
    if not context.behavior_engine_auto_detect:
        lines.append("- 꺼짐: Pandora/Nemesis는 수동 제외 옵션만 사용합니다.")
        return "\n".join(lines)

    has_pandora = any("pandora" in _entry_text(entry) for entry in context.executables)
    has_nemesis = any("nemesis" in _entry_text(entry) for entry in context.executables)

    if has_pandora and has_nemesis:
        lines.append("- Pandora와 Nemesis가 모두 등록되어 있어 둘 다 자동 추가하지 않습니다.")
        lines.append("- Pandora arguments 프리셋 덮어쓰기도 자동으로 제외합니다.")
    elif has_pandora:
        lines.append("- Pandora 등록됨: Nemesis 자동 추가를 자동으로 제외합니다.")
        lines.append("- Pandora arguments 프리셋 덮어쓰기도 자동으로 제외합니다.")
    elif has_nemesis:
        lines.append("- Nemesis 등록됨: Pandora 자동 추가를 자동으로 제외합니다.")
    else:
        lines.append("- 등록된 Pandora/Nemesis가 없어 누락 Executables 자동 추가 옵션을 그대로 따릅니다.")
    return "\n".join(lines)


def _format_preview_context(context: _PreviewContext) -> str:
    lines = [
        "[현재 감지된 경로]",
        f"- INI: {_display_path(context.ini_path)}",
        f"- 모드팩: {_display_path(context.instance_root)}",
        f"- Stock Game: {_display_path(context.game_path)}",
        f"- Tools: {_display_path(context.tool_root)}",
        "",
        _format_behavior_engine_detection(context),
        "",
        "[현재 등록된 실행 파일]",
    ]
    if not context.executables:
        lines.append("- 등록된 실행 파일을 찾지 못했습니다.")
    else:
        for entry in context.executables:
            title = entry.title or "(제목 없음)"
            lines.append(f"{entry.index}. {title}")
            if entry.binary:
                lines.append(f"   실행 파일: {_display_ini_value(entry.binary)}")
            if entry.working_directory:
                lines.append(f"   작업 폴더: {_display_ini_value(entry.working_directory)}")
    return "\n".join(lines)


def _format_run_output(
    *,
    dry_run: bool,
    context: _PreviewContext,
    discovery_warnings: tuple[str, ...],
    report: PatchReport,
) -> str:
    parts: list[str] = []

    if dry_run:
        parts.append(
            "\n".join(
                [
                    "이 화면은 전체 INI 파일 원문이 아니라 현재 상태 요약과 변경될 diff를 보여줍니다.",
                    "변경되지 않는 원본 줄은 diff 영역에서 생략될 수 있습니다.",
                    "",
                    _format_preview_context(context),
                ]
            )
        )

    if discovery_warnings:
        parts.append("[자동감지 경고]\n" + "\n".join(f"[warn] {w}" for w in discovery_warnings))

    summary = report.summary.rstrip("\n")
    if summary:
        parts.append("[적용 예정 요약]" if dry_run else "[실행 결과]")
        parts.append(summary)

    if report.diff:
        parts.append(
            "\n".join(
                [
                    "[변경 diff]",
                    "아래 diff에서 - 는 현재 파일, + 는 적용 후 내용입니다.",
                    "",
                    report.diff.rstrip("\n"),
                ]
            )
        )

    return "\n\n".join(p for p in parts if p) + "\n"


class _App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MO2 Path Wizard")
        self.geometry("1040x720")
        self.minsize(980, 660)

        self.pack_root = tk.StringVar()
        self.ini_path = tk.StringVar()
        self.instance_root = tk.StringVar()
        self.game_path = tk.StringVar()
        self.tool_root = tk.StringVar()

        self.apply_arg_presets = tk.BooleanVar(value=False)
        self.auto_add_missing = tk.BooleanVar(value=True)
        self.behavior_engine_auto_detect = tk.BooleanVar(value=True)
        self.skip_pandora = tk.BooleanVar(value=False)
        self.skip_nemesis = tk.BooleanVar(value=False)
        self.no_backup = tk.BooleanVar(value=False)

        self.lang = tk.StringVar(value="korean")
        self.edition = tk.StringVar(value="sse")
        self.args_json = tk.StringVar()

        self.show_advanced = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="준비됨")
        self._busy = False

        self._configure_style()
        self._build()

    def _pick_font_family(self, *candidates: str) -> str:
        families = {f.lower() for f in tkfont.families(self)}
        for name in candidates:
            if name.lower() in families:
                return name
        return "TkDefaultFont"

    def _configure_style(self) -> None:
        palette = {
            "bg": "#F4F6FA",
            "panel": "#FFFFFF",
            "panel_alt": "#F8FAFC",
            "text": "#111827",
            "muted": "#64748B",
            "line": "#D8DEE9",
            "accent": "#2563EB",
            "accent_hover": "#1D4ED8",
            "accent_dark": "#1E3A8A",
            "hero": "#172033",
            "hero_sub": "#CBD5E1",
            "console": "#0B1120",
            "console_text": "#D1D5DB",
        }
        self._palette = palette

        font_ui = self._pick_font_family("Segoe UI", "Inter", "Helvetica", "Arial")
        font_mono = self._pick_font_family("Cascadia Mono", "Consolas", "Menlo", "Courier New")

        self.option_add("*Font", (font_ui, 10))
        self.option_add("*Text.font", (font_mono, 10))

        style = ttk.Style(self)
        theme = "clam" if "clam" in style.theme_names() else style.theme_use()
        style.theme_use(theme)

        style.configure("App.TFrame", background=palette["bg"])
        style.configure("Card.TFrame", background=palette["panel"])
        style.configure("Output.TFrame", background=palette["console"])
        style.configure("Status.TFrame", background=palette["panel_alt"], relief="flat")

        style.configure("TLabel", background=palette["bg"], foreground=palette["text"])
        style.configure("Card.TLabel", background=palette["panel"], foreground=palette["text"])
        style.configure("Hint.TLabel", background=palette["panel"], foreground=palette["muted"], font=(font_ui, 9))
        style.configure("Header.TLabel", background=palette["bg"], foreground=palette["text"], font=(font_ui, 18, "bold"))
        style.configure("PanelTitle.TLabel", background=palette["bg"], foreground=palette["text"], font=(font_ui, 14, "bold"))
        style.configure("Subheader.TLabel", background=palette["bg"], foreground=palette["muted"], font=(font_ui, 10))
        style.configure("Status.TLabel", background=palette["panel_alt"], foreground=palette["muted"], font=(font_ui, 10))

        style.configure("Hero.TFrame", background=palette["hero"])
        style.configure("HeroTitle.TLabel", background=palette["hero"], foreground="#FFFFFF", font=(font_ui, 20, "bold"))
        style.configure("HeroSub.TLabel", background=palette["hero"], foreground=palette["hero_sub"], font=(font_ui, 10))
        style.configure(
            "HeroBadge.TLabel",
            background=palette["accent_dark"],
            foreground="#FFFFFF",
            font=(font_ui, 9, "bold"),
            padding=(12, 6),
        )

        style.configure("Card.TLabelframe", background=palette["panel"], bordercolor=palette["line"], padding=(14, 12))
        style.configure(
            "Card.TLabelframe.Label",
            background=palette["panel"],
            foreground=palette["text"],
            font=(font_ui, 10, "bold"),
        )

        style.configure("TCheckbutton", background=palette["bg"], foreground=palette["text"])
        style.configure("Card.TCheckbutton", background=palette["panel"], foreground=palette["text"])
        style.configure("TEntry", padding=(6, 4))
        style.configure("Path.TEntry", padding=(8, 6))
        style.configure("TButton", padding=(10, 6), font=(font_ui, 10))
        style.configure("Primary.TButton", padding=(16, 8), font=(font_ui, 10, "bold"), background=palette["accent"], foreground="#FFFFFF")
        style.configure("Secondary.TButton", padding=(16, 8), font=(font_ui, 10, "bold"))
        style.configure("Ghost.TButton", padding=(10, 5), font=(font_ui, 9))
        style.configure("Browse.TButton", padding=(9, 5), font=(font_ui, 9))
        style.map(
            "Primary.TButton",
            background=[("disabled", "#93C5FD"), ("pressed", palette["accent_dark"]), ("active", palette["accent_hover"])],
            foreground=[("disabled", "#EFF6FF"), ("pressed", "#FFFFFF"), ("active", "#FFFFFF")],
        )

        self.configure(background=palette["bg"])

    def _build(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=18)
        root.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        root.columnconfigure(0, weight=0, minsize=430)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        controls = ttk.Frame(root, style="App.TFrame")
        controls.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        controls.columnconfigure(0, weight=1)

        output_side = ttk.Frame(root, style="App.TFrame")
        output_side.grid(row=1, column=1, sticky="nsew")
        output_side.columnconfigure(0, weight=1)
        output_side.rowconfigure(1, weight=1)

        hero = ttk.Frame(root, style="Hero.TFrame", padding=(18, 14))
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="MO2 Path Wizard", style="HeroTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text="ModOrganizer.ini 경로와 실행 파일 설정을 안전하게 점검하고 적용합니다.",
            style="HeroSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(hero, text="MO2 종료 권장", style="HeroBadge.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

        modpack = ttk.Labelframe(controls, text="모드팩", style="Card.TLabelframe")
        modpack.grid(row=0, column=0, sticky="ew")
        modpack.columnconfigure(0, weight=1)

        self._path_row(modpack, "모드팩 폴더", self.pack_root, kind="dir", row=0)
        modpack_footer = ttk.Frame(modpack, style="Card.TFrame")
        modpack_footer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        modpack_footer.columnconfigure(0, weight=1)
        ttk.Label(modpack_footer, text="루트 폴더 선택 후 자동 감지를 실행하세요.", style="Hint.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.btn_auto_detect = ttk.Button(
            modpack_footer, text="자동 감지", style="Secondary.TButton", command=self._auto_detect
        )
        self.btn_auto_detect.grid(row=0, column=1, sticky="e", padx=(12, 0))

        options = ttk.Labelframe(controls, text="실행 옵션", style="Card.TLabelframe")
        options.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        options.columnconfigure(0, weight=1)

        option_grid = ttk.Frame(options, style="Card.TFrame")
        option_grid.grid(row=0, column=0, sticky="ew")
        option_grid.columnconfigure(0, weight=1)
        option_grid.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            option_grid, text="누락 Executables 자동 추가", variable=self.auto_add_missing, style="Card.TCheckbutton"
        ).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Checkbutton(
            option_grid, text="arguments 프리셋 적용", variable=self.apply_arg_presets, style="Card.TCheckbutton"
        ).grid(row=0, column=1, sticky="w", pady=3, padx=(12, 0))
        ttk.Checkbutton(
            option_grid,
            text="Pandora/Nemesis 자동 판단",
            variable=self.behavior_engine_auto_detect,
            style="Card.TCheckbutton",
        ).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Checkbutton(
            option_grid, text="백업(.bak) 만들지 않음", variable=self.no_backup, style="Card.TCheckbutton"
        ).grid(row=1, column=1, sticky="w", pady=3, padx=(12, 0))
        ttk.Checkbutton(
            option_grid,
            text="Pandora 강제 제외",
            variable=self.skip_pandora,
            style="Card.TCheckbutton",
        ).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Checkbutton(
            option_grid,
            text="Nemesis 강제 제외",
            variable=self.skip_nemesis,
            style="Card.TCheckbutton",
        ).grid(row=2, column=1, sticky="w", pady=3, padx=(12, 0))

        select_row = ttk.Frame(options, style="Card.TFrame")
        select_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(select_row, text="게임 에디션", style="Card.TLabel").pack(side="left")
        ttk.Combobox(select_row, textvariable=self.edition, values=["sse", "vr", "le"], width=6, state="readonly").pack(
            side="left", padx=(6, 14)
        )
        ttk.Label(select_row, text="xEdit 언어", style="Card.TLabel").pack(side="left")
        ttk.Combobox(select_row, textvariable=self.lang, values=["korean", "english"], width=12).pack(
            side="left", padx=(6, 0)
        )

        advanced_toggle = ttk.Frame(controls, style="App.TFrame")
        advanced_toggle.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(
            advanced_toggle, text="고급 경로 옵션 표시", variable=self.show_advanced, command=self._toggle_advanced
        ).pack(side="left")

        self.advanced_frame = ttk.Labelframe(controls, text="고급 경로", style="Card.TLabelframe")
        self.advanced_frame.columnconfigure(0, weight=1)
        self._path_row(self.advanced_frame, "ModOrganizer.ini", self.ini_path, kind="ini", row=0)
        self._path_row(self.advanced_frame, "인스턴스 루트", self.instance_root, kind="dir", row=1)
        self._path_row(self.advanced_frame, "Stock Game 경로", self.game_path, kind="dir", row=2)
        self._path_row(self.advanced_frame, "tools/Tool 경로", self.tool_root, kind="dir", row=3)
        self._path_row(self.advanced_frame, "args JSON(옵션)", self.args_json, kind="json", row=4)
        self.advanced_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.advanced_frame.grid_remove()

        actions = ttk.Frame(controls, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.btn_preview = ttk.Button(actions, text="미리보기", style="Secondary.TButton", command=self._preview)
        self.btn_preview.grid(row=0, column=0, sticky="ew")
        self.btn_apply = ttk.Button(actions, text="적용", style="Primary.TButton", command=self._apply)
        self.btn_apply.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        status_bar = ttk.Frame(root, style="Status.TFrame", padding=(12, 8))
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(status_bar, textvariable=self.status, style="Status.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(status_bar, mode="indeterminate", length=120)
        self.progress.pack(side="right")

        out_header = ttk.Frame(output_side, style="App.TFrame")
        out_header.grid(row=0, column=0, sticky="ew")
        ttk.Label(out_header, text="현재 상태 및 변경 미리보기", style="PanelTitle.TLabel").pack(side="left")
        ttk.Button(out_header, text="복사", style="Ghost.TButton", command=self._copy_output).pack(side="right")
        ttk.Button(out_header, text="지우기", style="Ghost.TButton", command=self._clear_output).pack(side="right", padx=(0, 8))

        out = ttk.Frame(output_side, style="Output.TFrame", padding=1)
        out.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        out.columnconfigure(0, weight=1)
        out.rowconfigure(0, weight=1)

        self.output = tk.Text(
            out,
            wrap="none",
            highlightthickness=0,
            borderwidth=0,
            padx=12,
            pady=10,
            background=self._palette["console"],
            foreground=self._palette["console_text"],
            insertbackground="#E5E7EB",
            selectbackground="#1D4ED8",
        )
        yscroll = ttk.Scrollbar(out, orient="vertical", command=self.output.yview)
        xscroll = ttk.Scrollbar(out, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.output.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        self.output.tag_configure("diff_add", foreground="#86EFAC")
        self.output.tag_configure("diff_del", foreground="#FDA4AF")
        self.output.tag_configure("diff_hunk", foreground="#93C5FD")
        self.output.tag_configure("diff_file", foreground="#CBD5E1")
        self.output.tag_configure("warn", foreground="#FBBF24")

        self.output.configure(state="disabled")

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, *, kind: str, row: int) -> None:
        r = ttk.Frame(parent, style="Card.TFrame")
        r.grid(row=row, column=0, sticky="ew", pady=4)
        r.columnconfigure(1, weight=1)

        ttk.Label(r, text=label, style="Card.TLabel", width=15).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(r, textvariable=var, style="Path.TEntry").grid(row=0, column=1, sticky="ew")
        ttk.Button(r, text="찾기", style="Browse.TButton", command=lambda: self._browse(var, kind)).grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )

    def _toggle_advanced(self) -> None:
        if bool(self.show_advanced.get()):
            self.advanced_frame.grid()
        else:
            self.advanced_frame.grid_remove()

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        if message is not None:
            self.status.set(message)

        state = "disabled" if busy else "normal"
        for w in (self.btn_auto_detect, self.btn_preview, self.btn_apply):
            try:
                w.configure(state=state)
            except Exception:
                pass

        if busy:
            try:
                self.progress.start(10)
            except Exception:
                pass
        else:
            try:
                self.progress.stop()
            except Exception:
                pass

    def _auto_detect(self) -> None:
        if self._busy:
            return

        root = Path(self.pack_root.get()).expanduser()
        if not root.is_dir():
            messagebox.showerror("오류", "모드팩 폴더를 먼저 선택해 주세요.")
            self.status.set("오류")
            return

        self._set_busy(True, "자동 감지 중...")

        def worker() -> None:
            try:
                discovered = discover_from_root(root, edition=self.edition.get().strip() or "sse")
            except Exception as e:
                self.after(0, lambda: self._on_detect_error(e))
                return
            self.after(0, lambda: self._on_detect_done(discovered))

        threading.Thread(target=worker, daemon=True).start()

    def _on_detect_done(self, discovered) -> None:
        self._set_busy(False)
        if discovered.ini_path:
            self.ini_path.set(str(discovered.ini_path))
        if discovered.instance_root:
            self.instance_root.set(str(discovered.instance_root))
        if discovered.game_path:
            self.game_path.set(str(discovered.game_path))
        if discovered.tool_root:
            self.tool_root.set(str(discovered.tool_root))

        if discovered.warnings:
            self._set_output("\n".join(f"[warn] {w}" for w in discovered.warnings) + "\n")
        self.status.set("자동 감지 완료")

    def _on_detect_error(self, exc: Exception) -> None:
        self._set_busy(False, "오류")
        messagebox.showerror("오류", str(exc))

    def _browse(self, var: tk.StringVar, kind: str) -> None:
        if kind == "ini":
            path = filedialog.askopenfilename(
                title="ModOrganizer.ini 선택",
                filetypes=[("INI", "*.ini"), ("All files", "*.*")],
            )
        elif kind == "json":
            path = filedialog.askopenfilename(
                title="args JSON 선택",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
        else:
            path = filedialog.askdirectory(title="폴더 선택")
        if path:
            var.set(path)

    def _clear_output(self) -> None:
        self._set_output("")

    def _tag_for_line(self, line: str) -> str | None:
        if line.startswith("[warn]"):
            return "warn"
        if line.startswith("@@"):
            return "diff_hunk"
        if line.startswith("+++ ") or line.startswith("--- "):
            return "diff_file"
        if line.startswith("+") and not line.startswith("+++"):
            return "diff_add"
        if line.startswith("-") and not line.startswith("---"):
            return "diff_del"
        return None

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        for line in text.splitlines(True):
            tag = self._tag_for_line(line)
            if tag:
                self.output.insert("end", line, tag)
            else:
                self.output.insert("end", line)
        self.output.configure(state="disabled")
        self.output.see("1.0" if not text else "end")

    def _copy_output(self) -> None:
        try:
            text = self.output.get("1.0", "end").rstrip("\n")
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status.set("출력 복사됨")
        except Exception:
            self.status.set("복사 실패")

    def _patch_job(self, dry_run: bool) -> tuple[object | None, _PreviewContext, PatchReport]:
        root = Path(self.pack_root.get()).expanduser() if self.pack_root.get().strip() else None
        discovered = None
        if root and root.is_dir():
            discovered = discover_from_root(root, edition=self.edition.get().strip() or "sse")

        ini = Path(self.ini_path.get()).expanduser() if self.ini_path.get().strip() else None
        if ini is None and discovered and discovered.ini_path:
            ini = discovered.ini_path
            self.ini_path.set(str(ini))
        if ini is None or not ini.exists():
            raise FileNotFoundError("ModOrganizer.ini를 찾지 못했습니다. (모드팩 폴더 또는 ini를 선택해 주세요)")

        instance_root = Path(self.instance_root.get()).expanduser() if self.instance_root.get().strip() else None
        if instance_root is None and discovered and discovered.instance_root:
            instance_root = discovered.instance_root
            self.instance_root.set(str(instance_root))

        game_path = Path(self.game_path.get()).expanduser() if self.game_path.get().strip() else None
        if game_path is None and discovered and discovered.game_path:
            game_path = discovered.game_path
            self.game_path.set(str(game_path))

        tool_root = Path(self.tool_root.get()).expanduser() if self.tool_root.get().strip() else None
        if tool_root is None and discovered and discovered.tool_root:
            tool_root = discovered.tool_root
            self.tool_root.set(str(tool_root))

        args_overrides: dict[str, str] = {}
        if self.args_json.get().strip():
            raw = json.loads(Path(self.args_json.get()).read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(k, str) and isinstance(v, str):
                        args_overrides[k.strip().lower()] = v

        skip_auto_add_titles: list[str] = []
        if self.skip_pandora.get():
            skip_auto_add_titles.append("Pandora Behaviour Engine+")
        if self.skip_nemesis.get():
            skip_auto_add_titles.append("Nemesis")

        options = PatchOptions(
            apply_arg_presets=bool(self.apply_arg_presets.get()),
            auto_add_missing=bool(self.auto_add_missing.get()),
            behavior_engine_auto_detect=bool(self.behavior_engine_auto_detect.get()),
            skip_auto_add_titles=tuple(skip_auto_add_titles),
            skip_arg_preset_titles=("Pandora Behaviour Engine+",) if self.skip_pandora.get() else (),
            language=self.lang.get().strip() or "korean",
            edition=self.edition.get().strip() or "sse",
            dry_run=dry_run,
            backup=not bool(self.no_backup.get()),
            non_interactive=True,
            args_overrides=args_overrides,
        )

        report = patch_modorganizer_ini(
            ini_path=ini,
            instance_root=instance_root,
            game_path=game_path,
            tool_root=tool_root,
            options=options,
        )
        context = _PreviewContext(
            ini_path=ini,
            instance_root=instance_root,
            game_path=game_path,
            tool_root=tool_root,
            executables=inspect_custom_executables(ini) if ini and ini.exists() else (),
            behavior_engine_auto_detect=bool(self.behavior_engine_auto_detect.get()),
        )
        return discovered, context, report

    def _run_async(self, *, dry_run: bool) -> None:
        if self._busy:
            return

        self._set_busy(True, "미리보기 생성 중..." if dry_run else "적용 중...")

        def worker() -> None:
            try:
                discovered, context, report = self._patch_job(dry_run=dry_run)
            except Exception as e:
                self.after(0, lambda: self._on_run_error(e))
                return
            self.after(
                0,
                lambda: self._on_run_done(
                    dry_run=dry_run,
                    discovered=discovered,
                    context=context,
                    report=report,
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_done(self, *, dry_run: bool, discovered, context: _PreviewContext, report: PatchReport) -> None:
        self._set_busy(False)

        warnings = tuple(getattr(discovered, "warnings", ()) or ())
        self._set_output(
            _format_run_output(
                dry_run=dry_run,
                context=context,
                discovery_warnings=warnings,
                report=report,
            )
        )

        if not report.ok:
            self.status.set("오류")
            messagebox.showerror("오류", report.summary)
            return
        self.status.set("미리보기 완료" if dry_run else "적용 완료")

    def _on_run_error(self, exc: Exception) -> None:
        self._set_busy(False, "오류")
        messagebox.showerror("오류", str(exc))

    def _preview(self) -> None:
        self._run_async(dry_run=True)

    def _apply(self) -> None:
        if messagebox.askyesno("확인", "정말 적용할까요? (MO2는 종료한 상태를 권장)"):
            self._run_async(dry_run=False)


def main() -> None:
    app = _App()
    app.mainloop()


if __name__ == "__main__":
    main()
