from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutableSpec:
    title: str
    exe_names: tuple[str, ...]
    kind: str  # "tool"(Tools 폴더 우선) | "mod"(mods 폴더 우선) | "instance"(모드팩 루트 바로 아래)
    dir_hints: tuple[str, ...] = ()
    hide: bool = False
    toolbar: bool = False
    ownicon: bool = False
    steam_app_id: str = ""


DEFAULT_EXECUTABLE_SPECS: tuple[ExecutableSpec, ...] = (
    ExecutableSpec(
        title="Edit",
        exe_names=("SSEEdit.exe", "SSEEdit64.exe", "xEdit.exe", "xEdit64.exe"),
        kind="tool",
        dir_hints=("sseedit", "xedit"),
    ),
    ExecutableSpec(
        title="Quick Auto Clean",
        exe_names=("SSEEditQuickAutoClean.exe", "xEditQuickAutoClean.exe"),
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
        # ParallaxGen은 0.9.0(2025-10)에서 PGPatcher로 이름이 바뀌었다.
        exe_names=("PGPatcher.exe", "ParallaxGen.exe"),
        kind="tool",
        dir_hints=("pgpatcher", "pg patcher", "parallaxgen", "paralaxgen", "proteus"),
    ),
    ExecutableSpec(
        title="BodySlide x64",
        exe_names=("BodySlide x64.exe",),
        kind="mod",
        dir_hints=("bodyslide and outfit studio", "bodyslide"),
    ),
    ExecutableSpec(
        title="Outfit Studio x64",
        exe_names=("OutfitStudio x64.exe",),
        kind="mod",
        dir_hints=("bodyslide and outfit studio", "outfit studio", "bodyslide"),
    ),
    ExecutableSpec(title="LOOT", exe_names=("LOOT.exe",), kind="tool", dir_hints=("loot",)),
    ExecutableSpec(title="BethINI", exe_names=("Bethini.exe",), kind="tool", dir_hints=("bethini",)),
    ExecutableSpec(title="zEdit", exe_names=("zEdit.exe",), kind="tool", dir_hints=("zedit",)),
    ExecutableSpec(
        title="SSE-AT", exe_names=("SSE-AT.exe",), kind="tool", dir_hints=("sse-at", "auto translator")
    ),
    ExecutableSpec(
        title="Dynamic Interface Patcher",
        exe_names=("DIP.exe",),
        kind="mod",
        dir_hints=("dynamic interface patcher",),
    ),
    ExecutableSpec(
        title="Cathedral Assets Optimizer",
        exe_names=("Cathedral_Assets_Optimizer.exe", "Cathedral Assets Optimizer.exe"),
        kind="tool",
        dir_hints=("cathedral",),
    ),
    ExecutableSpec(
        title="Explore Virtual Folder",
        exe_names=("Explorer++.exe",),
        kind="instance",
        dir_hints=("explorer++",),
    ),
)


class _FileIndex:
    """폴더 아래 파일 이름(소문자) -> 첫 경로. 같은 폴더를 여러 번 훑지 않도록 캐시한다."""

    def __init__(self) -> None:
        self._indexes: dict[tuple[str, int], dict[str, Path]] = {}

    def find(self, root: Path, filename: str, max_depth: int) -> Path | None:
        key = (str(root).lower(), max_depth)
        index = self._indexes.get(key)
        if index is None:
            index = {}
            # resolve()하지 않는다: 8.3 짧은 경로/subst 드라이브 표기를 그대로 유지해야 INI 경로가 섞이지 않는다.
            for dirpath, dirnames, filenames in os.walk(root):
                try:
                    depth = len(Path(dirpath).relative_to(root).parts)
                except ValueError:
                    depth = 0
                if depth >= max_depth:
                    dirnames[:] = []
                dirnames.sort()
                for f in filenames:
                    index.setdefault(f.lower(), Path(dirpath) / f)
            self._indexes[key] = index
        return index.get(filename.lower())


def locate_executable(
    spec: ExecutableSpec,
    *,
    instance_root: Path,
    tool_root: Path | None,
    max_depth: int = 4,
    index: _FileIndex | None = None,
) -> Path | None:
    idx = index or _FileIndex()

    def search_in_dir(root: Path) -> Path | None:
        for exe in spec.exe_names:
            direct = root / exe
            if direct.is_file():
                return direct
            found = idx.find(root, exe, max_depth)
            if found:
                return found
        return None

    def search_in_mods() -> Path | None:
        mods_root = instance_root / "mods"
        if not mods_root.is_dir() or not spec.dir_hints:
            return None
        hints = tuple(h.lower() for h in spec.dir_hints if h.strip())
        try:
            mod_dirs = sorted(d for d in mods_root.iterdir() if d.is_dir())
        except OSError:
            return None
        # 앞쪽 힌트(더 구체적인 이름)와 맞는 폴더부터 찾는다.
        for hint in hints:
            for mod_dir in mod_dirs:
                if hint in mod_dir.name.lower():
                    found = search_in_dir(mod_dir)
                    if found:
                        return found
        return None

    def search_in_tools() -> Path | None:
        if tool_root and tool_root.is_dir():
            return search_in_dir(tool_root)
        return None

    if spec.kind == "tool":
        # 일부 모드팩은 xEdit/DynDOLOD/xLODGen 등을 mods 폴더에 넣기도 함
        return search_in_tools() or search_in_mods()
    if spec.kind == "mod":
        # 일부 모드팩은 Nemesis/Pandora 등을 tools 폴더에 둘 수도 있음
        return search_in_mods() or search_in_tools()
    if spec.kind == "instance":
        for hint in spec.dir_hints:
            for exe in spec.exe_names:
                candidate = instance_root / hint / exe
                if candidate.is_file():
                    return candidate
        return None

    raise ValueError(f"Unknown spec.kind: {spec.kind}")
