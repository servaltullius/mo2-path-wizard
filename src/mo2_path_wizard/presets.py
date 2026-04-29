from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArgContext:
    instance_root: Path
    game_path: Path | None
    edition: str
    language: str

    @property
    def data_path(self) -> Path | None:
        if not self.game_path:
            return None
        return self.game_path / "Data"


def _escape_qsettings(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _win(path: Path) -> str:
    return str(path).replace("/", "\\")


def _fmt_args_qsettings(args: str) -> str:
    return _escape_qsettings(args)


def _edition_flag(ctx: ArgContext) -> str:
    if ctx.edition == "vr":
        return "-tesvvr"
    if ctx.edition == "le":
        return "-tesv"
    return "-sse"


def arg_preset_for_title(title: str, ctx: ArgContext) -> str | None:
    t = title.strip().lower()
    if not t:
        return None

    if "edit" in t or "xedit" in t:
        if not ctx.data_path:
            return None
        args = f'-D:"{_win(ctx.data_path)}" -l:{ctx.language}'
        return _fmt_args_qsettings(args)

    if "quick auto clean" in t or "quickautoclean" in t:
        if not ctx.data_path:
            return None
        args = f'-D:"{_win(ctx.data_path)}" -l:{ctx.language}'
        return _fmt_args_qsettings(args)

    if "texgen" in t or "dyndolod" in t or "xlodgen" in t or "xlodroad" in t:
        if not ctx.data_path:
            return None
        args = f'-d:"{_win(ctx.data_path)}" {_edition_flag(ctx)}'
        return _fmt_args_qsettings(args)

    if "pandora" in t:
        if not ctx.game_path:
            return None
        # 일반적으로 MO2 mods 아래 "Pandora Output"을 사용
        out_mod = ctx.instance_root / "mods" / "Pandora Output"
        args = f'--tesv:"{_win(ctx.game_path)}" -o:"{_win(out_mod)}"'
        return _fmt_args_qsettings(args)

    return None

