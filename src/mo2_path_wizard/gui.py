from __future__ import annotations

import json
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mo2_path_wizard.discovery import discover_from_root
from mo2_path_wizard.patcher import PatchOptions, PatchReport, patch_modorganizer_ini


class _App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MO2 Path Wizard")
        self.geometry("980x680")
        self.minsize(920, 620)

        self.pack_root = tk.StringVar()
        self.ini_path = tk.StringVar()
        self.instance_root = tk.StringVar()
        self.game_path = tk.StringVar()
        self.tool_root = tk.StringVar()

        self.apply_arg_presets = tk.BooleanVar(value=False)
        self.auto_add_missing = tk.BooleanVar(value=True)
        self.skip_pandora = tk.BooleanVar(value=False)
        self.no_backup = tk.BooleanVar(value=False)

        self.lang = tk.StringVar(value="korean")
        self.edition = tk.StringVar(value="sse")
        self.args_json = tk.StringVar()

        self.show_advanced = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ready")
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
        bg = "#F6F7FB"
        card = "#FFFFFF"
        text = "#111827"
        muted = "#6B7280"

        font_ui = self._pick_font_family("Segoe UI", "Inter", "Helvetica", "Arial")
        font_mono = self._pick_font_family("Cascadia Mono", "Consolas", "Menlo", "Courier New")

        self.option_add("*Font", (font_ui, 10))
        self.option_add("*Text.font", (font_mono, 10))

        style = ttk.Style(self)
        theme = "clam" if "clam" in style.theme_names() else style.theme_use()
        style.theme_use(theme)

        style.configure("App.TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Card.TLabel", background=card, foreground=text)
        style.configure("Header.TLabel", background=bg, foreground=text, font=(font_ui, 18, "bold"))
        style.configure("Subheader.TLabel", background=bg, foreground=muted, font=(font_ui, 10))

        style.configure("Card.TLabelframe", background=card, padding=(12, 10))
        style.configure("Card.TLabelframe.Label", background=card, foreground=text, font=(font_ui, 10, "bold"))

        style.configure("TCheckbutton", background=bg)
        style.configure("Card.TCheckbutton", background=card)
        style.configure("TEntry", padding=(6, 4))
        style.configure("TButton", padding=(10, 6))

        self.configure(background=bg)

    def _build(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=16)
        root.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        controls = ttk.Frame(root, style="App.TFrame")
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        controls.columnconfigure(0, weight=1)

        output_side = ttk.Frame(root, style="App.TFrame")
        output_side.grid(row=0, column=1, sticky="nsew")
        output_side.columnconfigure(0, weight=1)
        output_side.rowconfigure(1, weight=1)

        ttk.Label(controls, text="MO2 Path Wizard", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            controls,
            text="ModOrganizer.ini 경로/Executables 자동 복구 도구 (Preview → Apply)",
            style="Subheader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        modpack = ttk.Labelframe(controls, text="Modpack", style="Card.TLabelframe")
        modpack.grid(row=2, column=0, sticky="ew")
        modpack.columnconfigure(0, weight=1)

        self._path_row(modpack, "모드팩 폴더", self.pack_root, kind="dir", row=0)
        self.btn_auto_detect = ttk.Button(modpack, text="자동 감지", command=self._auto_detect)
        self.btn_auto_detect.grid(row=1, column=0, sticky="e", pady=(8, 0))

        options = ttk.Labelframe(controls, text="Options", style="Card.TLabelframe")
        options.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        options.columnconfigure(0, weight=1)

        chk_row = ttk.Frame(options, style="Card.TFrame")
        chk_row.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(
            chk_row, text="누락 Executables 자동 추가", variable=self.auto_add_missing, style="Card.TCheckbutton"
        ).pack(side="left")
        ttk.Checkbutton(
            chk_row, text="arguments 프리셋 적용(덮어쓰기)", variable=self.apply_arg_presets, style="Card.TCheckbutton"
        ).pack(
            side="left", padx=(10, 0)
        )
        ttk.Checkbutton(chk_row, text="백업(.bak) 만들지 않음", variable=self.no_backup, style="Card.TCheckbutton").pack(
            side="left", padx=(10, 0)
        )

        skip_row = ttk.Frame(options, style="Card.TFrame")
        skip_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(
            skip_row,
            text="Pandora 자동 추가/프리셋 제외",
            variable=self.skip_pandora,
            style="Card.TCheckbutton",
        ).pack(side="left")

        select_row = ttk.Frame(options, style="Card.TFrame")
        select_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(select_row, text="에디션", style="Card.TLabel").pack(side="left")
        ttk.Combobox(select_row, textvariable=self.edition, values=["sse", "vr", "le"], width=6, state="readonly").pack(
            side="left", padx=(6, 14)
        )
        ttk.Label(select_row, text="xEdit 언어", style="Card.TLabel").pack(side="left")
        ttk.Combobox(select_row, textvariable=self.lang, values=["korean", "english"], width=12).pack(
            side="left", padx=(6, 0)
        )

        advanced_toggle = ttk.Frame(controls, style="App.TFrame")
        advanced_toggle.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(
            advanced_toggle, text="고급 경로 옵션 표시", variable=self.show_advanced, command=self._toggle_advanced
        ).pack(side="left")

        self.advanced_frame = ttk.Labelframe(controls, text="Advanced Paths", style="Card.TLabelframe")
        self.advanced_frame.columnconfigure(0, weight=1)
        self._path_row(self.advanced_frame, "ModOrganizer.ini", self.ini_path, kind="ini", row=0)
        self._path_row(self.advanced_frame, "인스턴스 루트", self.instance_root, kind="dir", row=1)
        self._path_row(self.advanced_frame, "Stock Game 경로", self.game_path, kind="dir", row=2)
        self._path_row(self.advanced_frame, "tools/Tool 경로", self.tool_root, kind="dir", row=3)
        self._path_row(self.advanced_frame, "args JSON(옵션)", self.args_json, kind="json", row=4)
        self.advanced_frame.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.advanced_frame.grid_remove()

        actions = ttk.Frame(controls, style="App.TFrame")
        actions.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        self.btn_preview = ttk.Button(actions, text="미리보기(Preview)", command=self._preview)
        self.btn_preview.pack(side="left")
        self.btn_apply = ttk.Button(actions, text="적용(Apply)", command=self._apply)
        self.btn_apply.pack(side="left", padx=(10, 0))

        status_bar = ttk.Frame(root, style="App.TFrame")
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(status_bar, textvariable=self.status, style="Subheader.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(status_bar, mode="indeterminate", length=120)
        self.progress.pack(side="right")

        out_header = ttk.Frame(output_side, style="App.TFrame")
        out_header.grid(row=0, column=0, sticky="ew")
        ttk.Label(out_header, text="Output", style="Header.TLabel").pack(side="left")
        ttk.Button(out_header, text="복사", command=self._copy_output).pack(side="right")
        ttk.Button(out_header, text="지우기", command=self._clear_output).pack(side="right", padx=(0, 8))

        out = ttk.Frame(output_side, style="Card.TFrame")
        out.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        out.columnconfigure(0, weight=1)
        out.rowconfigure(0, weight=1)

        self.output = tk.Text(
            out,
            wrap="none",
            highlightthickness=0,
            borderwidth=0,
            background="#FFFFFF",
            foreground="#111827",
            insertbackground="#111827",
            selectbackground="#DBEAFE",
        )
        yscroll = ttk.Scrollbar(out, orient="vertical", command=self.output.yview)
        xscroll = ttk.Scrollbar(out, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.output.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        self.output.tag_configure("diff_add", foreground="#166534")
        self.output.tag_configure("diff_del", foreground="#B91C1C")
        self.output.tag_configure("diff_hunk", foreground="#1D4ED8")
        self.output.tag_configure("diff_file", foreground="#374151")
        self.output.tag_configure("warn", foreground="#B45309")

        self.output.configure(state="disabled")

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, *, kind: str, row: int) -> None:
        r = ttk.Frame(parent, style="Card.TFrame")
        r.grid(row=row, column=0, sticky="ew", pady=4)
        r.columnconfigure(1, weight=1)

        ttk.Label(r, text=label, style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(r, textvariable=var).grid(row=0, column=1, sticky="ew")
        ttk.Button(r, text="찾기...", command=lambda: self._browse(var, kind)).grid(row=0, column=2, sticky="e", padx=(8, 0))

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
            self.status.set("Error")
            return

        self._set_busy(True, "Detecting...")

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
        self.status.set("Auto-detect complete")

    def _on_detect_error(self, exc: Exception) -> None:
        self._set_busy(False, "Error")
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
            self.status.set("Output copied to clipboard")
        except Exception:
            self.status.set("Copy failed")

    def _patch_job(self, dry_run: bool) -> tuple[object | None, PatchReport]:
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

        options = PatchOptions(
            apply_arg_presets=bool(self.apply_arg_presets.get()),
            auto_add_missing=bool(self.auto_add_missing.get()),
            skip_auto_add_titles=("Pandora Behaviour Engine+",) if self.skip_pandora.get() else (),
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
        return discovered, report

    def _run_async(self, *, dry_run: bool) -> None:
        if self._busy:
            return

        self._set_busy(True, "Running..." if dry_run else "Applying...")

        def worker() -> None:
            try:
                discovered, report = self._patch_job(dry_run=dry_run)
            except Exception as e:
                self.after(0, lambda: self._on_run_error(e))
                return
            self.after(0, lambda: self._on_run_done(dry_run=dry_run, discovered=discovered, report=report))

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_done(self, *, dry_run: bool, discovered, report: PatchReport) -> None:
        self._set_busy(False)

        parts: list[str] = []
        if discovered and getattr(discovered, "warnings", None):
            parts.append("\n".join(f"[warn] {w}" for w in discovered.warnings))
        if report.diff:
            parts.append(report.diff.rstrip("\n"))
        parts.append(report.summary.rstrip("\n"))
        self._set_output("\n\n".join(p for p in parts if p) + "\n")

        if not report.ok:
            self.status.set("Error")
            messagebox.showerror("오류", report.summary)
            return
        self.status.set("Preview complete" if dry_run else "Done")

    def _on_run_error(self, exc: Exception) -> None:
        self._set_busy(False, "Error")
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
