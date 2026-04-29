from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutableSpec:
    title: str
    exe_names: tuple[str, ...]
    kind: str  # "tool" | "mod"
    dir_hints: tuple[str, ...] = ()
    hide: bool = False
    toolbar: bool = False
    ownicon: bool = False
    steam_app_id: str = ""


DEFAULT_EXECUTABLE_SPECS: tuple[ExecutableSpec, ...] = (
    ExecutableSpec(title="Edit", exe_names=("SSEEdit.exe",), kind="tool", dir_hints=("sseedit", "xedit")),
    ExecutableSpec(
        title="Quick Auto Clean",
        exe_names=("SSEEditQuickAutoClean.exe",),
        kind="tool",
        dir_hints=("sseedit", "xedit"),
    ),
    ExecutableSpec(title="TexGen", exe_names=("TexGenx64.exe",), kind="tool", dir_hints=("texgen", "dyndolod")),
    ExecutableSpec(title="DynDOLOD", exe_names=("DynDOLODx64.exe",), kind="tool", dir_hints=("dyndolod",)),
    ExecutableSpec(
        title="xLODGen", exe_names=("xLODGenx64.exe", "SSELODGenx64.exe"), kind="tool", dir_hints=("xlodgen",)
    ),
    ExecutableSpec(title="Synthesis", exe_names=("Synthesis.exe",), kind="tool", dir_hints=("synthesis",)),
    ExecutableSpec(
        title="Nemesis",
        exe_names=("Nemesis Unlimited Behavior Engine.exe",),
        kind="mod",
        dir_hints=("nemesis",),
        toolbar=True,
    ),
    ExecutableSpec(
        title="Pandora Behaviour Engine+",
        exe_names=("Pandora Behaviour Engine+.exe", "Pandora Behaviour Engine.exe"),
        kind="mod",
        dir_hints=("pandora",),
        toolbar=True,
    ),
    ExecutableSpec(
        title="PGPatcher",
        exe_names=("PGPatcher.exe",),
        kind="mod",
        dir_hints=("pgpatcher", "pg patcher", "proteus"),
    ),
)


def _find_file_depth(root: Path, filename: str, max_depth: int) -> Path | None:
    filename_l = filename.lower()
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        try:
            rel = Path(dirpath).resolve().relative_to(root)
            depth = len(rel.parts)
        except Exception:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        for f in filenames:
            if f.lower() == filename_l:
                return Path(dirpath) / f
    return None


def locate_executable(
    spec: ExecutableSpec,
    *,
    instance_root: Path,
    tool_root: Path | None,
    max_depth: int = 4,
) -> Path | None:
    def search_in_dir(root: Path) -> Path | None:
        for exe in spec.exe_names:
            direct = root / exe
            if direct.is_file():
                return direct
            found = _find_file_depth(root, exe, max_depth=max_depth)
            if found:
                return found
        return None

    def search_in_mods() -> Path | None:
        mods_root = instance_root / "mods"
        if not mods_root.is_dir():
            return None

        hints = tuple(h.lower() for h in spec.dir_hints if h.strip())
        candidates = [d for d in mods_root.iterdir() if d.is_dir()]
        if hints:
            candidates = [d for d in candidates if any(h in d.name.lower() for h in hints)]

        for mod_dir in candidates:
            found = search_in_dir(mod_dir)
            if found:
                return found
        return None

    if spec.kind == "tool":
        if tool_root and tool_root.is_dir():
            found = search_in_dir(tool_root)
            if found:
                return found
        # 일부 모드팩은 xEdit/DynDOLOD/xLODGen 등을 mods 폴더에 넣기도 함
        return search_in_mods()

    if spec.kind == "mod":
        mods_root = instance_root / "mods"
        if not mods_root.is_dir():
            mods_root = None

        mod_dirs: list[Path] = []
        hints = tuple(h.lower() for h in spec.dir_hints if h.strip())
        if mods_root:
            if hints:
                for d in mods_root.iterdir():
                    if d.is_dir():
                        name_l = d.name.lower()
                        if any(h in name_l for h in hints):
                            mod_dirs.append(d)
            if not mod_dirs and hints:
                mod_dirs = []
            elif not mod_dirs:
                mod_dirs = [d for d in mods_root.iterdir() if d.is_dir()]

            for mod_dir in mod_dirs:
                found = search_in_dir(mod_dir)
                if found:
                    return found

        # 일부 모드팩은 Nemesis/Pandora 등을 tools 폴더에 둘 수도 있음
        if tool_root and tool_root.is_dir():
            found = search_in_dir(tool_root)
            if found:
                return found
        return None

    raise ValueError(f"Unknown spec.kind: {spec.kind}")
