from __future__ import annotations

import re
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
        return "-tes5vr"
    if ctx.edition == "le":
        return "-tes5"
    return "-sse"


# 프리셋은 실행 파일 이름으로 판정한다. title의 "edit" 부분 일치는
# "Skyrim Special Edition", "zEdit" 같은 항목까지 xEdit으로 오인한다.
_GAME_EXES = frozenset(
    {
        "skyrimse.exe",
        "skyrimselauncher.exe",
        "skyrimvr.exe",
        "skyrimvrlauncher.exe",
        "tesv.exe",
        "skyrimlauncher.exe",
        "skse64_loader.exe",
        "sksevr_loader.exe",
        "skse_loader.exe",
    }
)
_XEDIT_EXE_RE = re.compile(r"^(?:x|sse|tes5|tes5vr)?edit(?:64)?(?:quickautoclean(?:64)?)?\.exe$", re.IGNORECASE)
_LODGEN_EXE_RE = re.compile(r"^(?:dyndolod|texgen|xlodgen)(?:x64)?\.exe$", re.IGNORECASE)
_XEDIT_TITLE_RE = re.compile(r"\b(?:x|sse|tes5|tes5vr)?edit(?:64)?\b", re.IGNORECASE)
_LODGEN_TITLE_RE = re.compile(r"texgen|dyndolod|xlodgen|xlodroad", re.IGNORECASE)


def _binary_basename(binary: str) -> str:
    return binary.strip().strip('"').replace("\\", "/").rstrip("/").split("/")[-1]


def classify_tool(title: str, binary: str = "") -> str | None:
    """실행 항목이 어떤 프리셋 대상인지 판정한다: "xedit" | "lodgen" | "pandora" | None.

    binary가 있으면 실행 파일 이름만으로 판정하고, 비어 있을 때만 title을 본다.
    """
    name = _binary_basename(binary)
    if name:
        lower = name.lower()
        if lower in _GAME_EXES:
            return None
        if _XEDIT_EXE_RE.match(name):
            return "xedit"
        if _LODGEN_EXE_RE.match(name):
            return "lodgen"
        if "pandora" in lower and lower.endswith(".exe"):
            return "pandora"
        return None

    t = title.strip()
    if not t:
        return None
    if _LODGEN_TITLE_RE.search(t):
        return "lodgen"
    if "pandora" in t.lower():
        return "pandora"
    if _XEDIT_TITLE_RE.search(t):
        return "xedit"
    return None


def arg_preset_for(title: str, binary: str, ctx: ArgContext) -> str | None:
    kind = classify_tool(title, binary)

    if kind == "xedit":
        if not ctx.data_path:
            return None
        args = f'-D:"{_win(ctx.data_path)}" -l:{ctx.language}'
        # xEdit은 실행 파일 이름으로 게임 모드를 정한다. xEdit.exe처럼 이름을 바꾼 경우 명시가 필요하다.
        if _binary_basename(binary).lower().startswith("xedit"):
            args = f"{_edition_flag(ctx)} {args}"
        return _fmt_args_qsettings(args)

    if kind == "lodgen":
        if not ctx.data_path:
            return None
        args = f'-d:"{_win(ctx.data_path)}" {_edition_flag(ctx)}'
        return _fmt_args_qsettings(args)

    if kind == "pandora":
        if not ctx.game_path:
            return None
        # 일반적으로 MO2 mods 아래 "Pandora Output"을 사용
        out_mod = ctx.instance_root / "mods" / "Pandora Output"
        args = f'--tesv:"{_win(ctx.game_path)}" -o:"{_win(out_mod)}"'
        return _fmt_args_qsettings(args)

    return None


def edition_from_game_name(game_name: str) -> str:
    """MO2 INI의 [General] gameName으로 에디션을 정한다(모르면 sse)."""
    name = game_name.strip().lower()
    if "vr" in name.split() or name.endswith(" vr"):
        return "vr"
    if name in ("skyrim", "enderal"):
        return "le"
    return "sse"
