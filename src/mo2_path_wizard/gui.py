from __future__ import annotations

import json
import threading
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mo2_path_wizard.discovery import discover_from_root
from mo2_path_wizard.external import describe_changes
from mo2_path_wizard.mo2proc import Mo2Status, check_mo2_status
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
    mo2_status: Mo2Status | None = None
    missing_indices: frozenset[int] = frozenset()


class _Mo2RunningError(RuntimeError):
    """같은 모드팩의 MO2가 실행 중이라 적용을 멈췄다."""


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


def _format_mo2_status(status: Mo2Status | None) -> str:
    lines = ["[MO2 실행 상태]"]
    if status is None or not status.supported:
        lines.append("- 확인할 수 없음(Windows에서만 확인합니다). 적용 전에 MO2를 종료해 주세요.")
    elif status.same_instance:
        lines.append("- 이 모드팩의 MO2가 실행 중입니다. 적용하기 전에 MO2를 종료해 주세요.")
        lines.append("  (MO2는 종료할 때 ModOrganizer.ini를 다시 써서 변경을 덮어씁니다)")
    elif status.any_running:
        lines.append("- 다른 MO2가 실행 중입니다: " + ", ".join(str(p) for p in status.running))
    else:
        lines.append("- 실행 중인 MO2 없음")
    return "\n".join(lines)


def _format_preview_context(context: _PreviewContext) -> str:
    lines = [
        _format_mo2_status(context.mo2_status),
        "",
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
            mark = "  [warn] 실행 파일 없음" if entry.index in context.missing_indices else ""
            lines.append(f"{entry.index}. {title}{mark}")
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

    if report.external:
        parts.append(
            "[외부 툴 설정 파일]\n"
            "DynDOLOD/BodySlide/Synthesis 등 툴 설정에 남은 옛 경로입니다. 적용하면 각 파일 옆에 .bak 백업을 만듭니다.\n\n"
            + describe_changes(report.external)
        )

    if report.missing_binaries:
        parts.append(
            "[실행 파일이 없는 항목]\n"
            "적용 후에도 실행 파일을 찾을 수 없습니다. MO2에서 경로를 확인하거나 항목을 정리해 주세요.\n"
            + "\n".join(f"[warn] {e.index}. {e.title}: {_display_ini_value(e.binary)}" for e in report.missing_binaries)
        )

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
        self.external_configs = tk.BooleanVar(value=True)
        self.overwrite_existing_args = tk.BooleanVar(value=False)
        self.auto_add_missing = tk.BooleanVar(value=True)
        self.behavior_engine_auto_detect = tk.BooleanVar(value=True)
        self.skip_pandora = tk.BooleanVar(value=False)
        self.skip_nemesis = tk.BooleanVar(value=False)
        self.no_backup = tk.BooleanVar(value=False)

        self.lang = tk.StringVar(value="korean")
        self.edition = tk.StringVar(value="auto")
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

        controls_side = ttk.Frame(root, style="App.TFrame")
        controls_side.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        controls_side.columnconfigure(0, weight=1)
        controls_side.rowconfigure(0, weight=1)
        # 설정 카드들은 스크롤 영역에 넣고, 미리보기/적용 버튼은 그 아래에 고정한다.
        # (창이 작거나 고급 경로를 펼쳐도 실행 버튼이 화면 밖으로 밀려나지 않도록)
        controls = self._build_scroll_area(controls_side)

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
        self.modpack_hint = ttk.Label(
            modpack_footer,
            text="폴더 선택 후 바로 미리보기를 누르면 자동 감지까지 함께 실행됩니다.",
            style="Hint.TLabel",
        )
        self.modpack_hint.grid(row=0, column=0, sticky="w")
        self.btn_auto_detect = ttk.Button(
            modpack_footer, text="경로만 자동 감지", style="Secondary.TButton", command=self._auto_detect
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
        ttk.Checkbutton(
            option_grid,
            text="기존 arguments도 프리셋으로 덮어쓰기",
            variable=self.overwrite_existing_args,
            style="Card.TCheckbutton",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Checkbutton(
            option_grid,
            text="툴 설정 파일(DynDOLOD·BodySlide·Synthesis 등)의 옛 경로도 고치기",
            variable=self.external_configs,
            style="Card.TCheckbutton",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=3)

        select_row = ttk.Frame(options, style="Card.TFrame")
        select_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(select_row, text="게임 에디션", style="Card.TLabel").pack(side="left")
        ttk.Combobox(select_row, textvariable=self.edition, values=["auto", "sse", "vr", "le"], width=6, state="readonly").pack(
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

        actions = ttk.Frame(controls_side, style="App.TFrame")
        actions.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.btn_preview = ttk.Button(actions, text="자동 감지 + 미리보기", style="Secondary.TButton", command=self._preview)
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
        # 폭이 모자라면 나중에 pack한 위젯부터 잘리므로, 버튼을 먼저 놓고 제목을 마지막에 놓는다.
        ttk.Button(out_header, text="복사", style="Ghost.TButton", command=self._copy_output).pack(side="right")
        ttk.Button(out_header, text="지우기", style="Ghost.TButton", command=self._clear_output).pack(side="right", padx=(0, 8))
        ttk.Label(out_header, text="현재 상태 및 변경 미리보기", style="PanelTitle.TLabel").pack(side="left")

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

    def _build_scroll_area(self, parent: ttk.Frame) -> ttk.Frame:
        """세로 스크롤되는 영역을 만들고 그 안쪽 프레임을 돌려준다. 내용이 넘칠 때만 스크롤바를 보인다."""
        area = ttk.Frame(parent, style="App.TFrame")
        area.grid(row=0, column=0, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)

        canvas = tk.Canvas(area, highlightthickness=0, borderwidth=0, background=self._palette["bg"])
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ttk.Frame(canvas, style="App.TFrame")
        inner.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def sync(_event=None) -> None:
            canvas.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()))
            canvas.configure(width=inner.winfo_reqwidth())
            canvas.itemconfigure(window, width=max(canvas.winfo_width(), inner.winfo_reqwidth()))
            if inner.winfo_reqheight() > canvas.winfo_height() > 1:
                scrollbar.grid()
            else:
                scrollbar.grid_remove()
                canvas.yview_moveto(0)

        inner.bind("<Configure>", sync)
        canvas.bind("<Configure>", sync)

        def on_wheel(event: tk.Event) -> str | None:
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return None
            step = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
            canvas.yview_scroll(step * 3, "units")
            return "break"

        # 마우스가 설정 영역 위에 있을 때만 휠로 스크롤한다(오른쪽 출력 창 스크롤과 겹치지 않게).
        def bind_wheel(_event=None) -> None:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.bind_all(seq, on_wheel)

        def unbind_wheel(_event=None) -> None:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.unbind_all(seq)

        area.bind("<Enter>", bind_wheel)
        area.bind("<Leave>", unbind_wheel)

        self._controls_canvas = canvas
        self._controls_sync = sync
        return inner

    def _toggle_advanced(self) -> None:
        if bool(self.show_advanced.get()):
            self.advanced_frame.grid()
            # 펼친 고급 경로가 보이도록 아래로 스크롤
            self.update_idletasks()
            self._controls_sync()
            self._controls_canvas.yview_moveto(1.0)
        else:
            self.advanced_frame.grid_remove()
            self.update_idletasks()
            self._controls_sync()

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
        edition = self.edition.get().strip() or "auto"

        def worker() -> None:
            try:
                discovered = discover_from_root(root, edition=edition)
            except Exception as e:
                # except 블록이 끝나면 e가 지워지므로 기본 인자로 묶어 둔다.
                self.after(0, lambda exc=e: self._on_detect_error(exc))
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
        if line.startswith("[warn]") or "[warn]" in line or line.startswith("- warn:"):
            return "warn"
        if line.startswith("    - "):
            return "diff_del"
        if line.startswith("    + "):
            return "diff_add"
        if line.startswith(("- ", "+ ")):
            return None
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

    def _snapshot_inputs(self, dry_run: bool, force: bool = False) -> dict:
        """Tk 변수는 메인 스레드에서만 읽는다. 작업 스레드에는 이 스냅샷만 넘긴다."""

        def opt_path(var: tk.StringVar) -> Path | None:
            v = var.get().strip()
            return Path(v).expanduser() if v else None

        return {
            "dry_run": dry_run,
            "force": force,
            "external_configs": bool(self.external_configs.get()),
            "pack_root": opt_path(self.pack_root),
            "ini": opt_path(self.ini_path),
            "instance_root": opt_path(self.instance_root),
            "game_path": opt_path(self.game_path),
            "tool_root": opt_path(self.tool_root),
            "args_json": opt_path(self.args_json),
            "edition": self.edition.get().strip() or "auto",
            "language": self.lang.get().strip() or "korean",
            "apply_arg_presets": bool(self.apply_arg_presets.get()),
            "overwrite_existing_args": bool(self.overwrite_existing_args.get()),
            "auto_add_missing": bool(self.auto_add_missing.get()),
            "behavior_engine_auto_detect": bool(self.behavior_engine_auto_detect.get()),
            "skip_pandora": bool(self.skip_pandora.get()),
            "skip_nemesis": bool(self.skip_nemesis.get()),
            "backup": not bool(self.no_backup.get()),
        }

    @staticmethod
    def _patch_job(inputs: dict) -> tuple[object | None, _PreviewContext, PatchReport]:
        root = inputs["pack_root"]
        discovered = None
        if root and root.is_dir():
            discovered = discover_from_root(root, edition=inputs["edition"])

        ini = inputs["ini"]
        if ini is None and discovered and discovered.ini_path:
            ini = discovered.ini_path
        if ini is None or not ini.exists():
            raise FileNotFoundError("ModOrganizer.ini를 찾지 못했습니다. (모드팩 폴더 또는 ini를 선택해 주세요)")

        mo2_status = check_mo2_status(ini)
        if not inputs["dry_run"] and mo2_status.same_instance and not inputs["force"]:
            raise _Mo2RunningError("이 모드팩의 MO2가 실행 중입니다.")

        edition = inputs["edition"]
        if edition == "auto" and discovered is not None:
            edition = discovered.edition

        instance_root = inputs["instance_root"]
        if instance_root is None and discovered and discovered.instance_root:
            instance_root = discovered.instance_root

        game_path = inputs["game_path"]
        if game_path is None and discovered and discovered.game_path:
            game_path = discovered.game_path

        tool_root = inputs["tool_root"]
        if tool_root is None and discovered and discovered.tool_root:
            tool_root = discovered.tool_root

        args_overrides: dict[str, str] = {}
        if inputs["args_json"]:
            try:
                raw = json.loads(inputs["args_json"].read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise ValueError(f"arguments JSON을 읽지 못했습니다: {e}") from e
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(k, str) and isinstance(v, str):
                        args_overrides[k.strip().lower()] = v

        skip_auto_add_titles: list[str] = []
        if inputs["skip_pandora"]:
            skip_auto_add_titles.append("Pandora Behaviour Engine+")
        if inputs["skip_nemesis"]:
            skip_auto_add_titles.append("Nemesis")

        options = PatchOptions(
            apply_arg_presets=inputs["apply_arg_presets"],
            overwrite_existing_args=inputs["overwrite_existing_args"],
            auto_add_missing=inputs["auto_add_missing"],
            behavior_engine_auto_detect=inputs["behavior_engine_auto_detect"],
            skip_auto_add_titles=tuple(skip_auto_add_titles),
            skip_arg_preset_titles=("Pandora Behaviour Engine+",) if inputs["skip_pandora"] else (),
            language=inputs["language"],
            edition=edition,
            dry_run=inputs["dry_run"],
            external_configs=inputs["external_configs"],
            backup=inputs["backup"],
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
            behavior_engine_auto_detect=inputs["behavior_engine_auto_detect"],
            mo2_status=mo2_status,
            missing_indices=frozenset(e.index for e in report.missing_binaries),
        )
        return discovered, context, report

    def _run_async(self, *, dry_run: bool, force: bool = False) -> None:
        if self._busy:
            return

        self._set_busy(True, "자동 감지 + 미리보기 중..." if dry_run else "자동 감지 + 적용 중...")
        inputs = self._snapshot_inputs(dry_run, force)

        def worker() -> None:
            try:
                discovered, context, report = self._patch_job(inputs)
            except Exception as e:
                # except 블록이 끝나면 e가 지워지므로 기본 인자로 묶어 둔다.
                self.after(0, lambda exc=e: self._on_run_error(exc))
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

        # 자동 감지로 채운 경로를 입력 칸에 반영(메인 스레드)
        for var, value in (
            (self.ini_path, context.ini_path),
            (self.instance_root, context.instance_root),
            (self.game_path, context.game_path),
            (self.tool_root, context.tool_root),
        ):
            if value is not None and not var.get().strip():
                var.set(str(value))

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
        if isinstance(exc, _Mo2RunningError):
            self._set_busy(False, "MO2 실행 중")
            proceed = messagebox.askyesno(
                "MO2 실행 중",
                "이 모드팩의 MO2가 실행 중입니다.\n"
                "MO2는 종료할 때 ModOrganizer.ini를 다시 써서 지금 적용한 변경을 덮어씁니다.\n\n"
                "MO2를 종료한 뒤 다시 적용하는 것을 권장합니다.\n"
                "그래도 지금 적용할까요?",
                icon="warning",
                default="no",
            )
            if proceed:
                self._run_async(dry_run=False, force=True)
            return
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
