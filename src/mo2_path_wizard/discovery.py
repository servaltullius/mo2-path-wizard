from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredPaths:
    root: Path
    ini_path: Path | None
    instance_root: Path | None
    game_path: Path | None
    tool_root: Path | None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.ini_path is not None and self.instance_root is not None


_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")
_CUSTOM_BINARY_RE = re.compile(r"^\d+\\binary=(?P<value>.*)$")


def _normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def _parse_bytearray_path(value: str) -> str | None:
    v = value.strip()
    if not (v.startswith("@ByteArray(") and v.endswith(")")):
        return None
    inner = v[len("@ByteArray(") : -1]
    return inner.replace("\\\\", "\\")


def _real_case_path(path: Path) -> Path:
    """
    Windows/DrvFS 같은 case-insensitive 환경에서, 실제 디스크에 저장된 대소문자 표기를 최대한 유지합니다.
    (예: 'Stock Game' -> 'STOCK GAME')
    """
    try:
        parent = path.parent
        name = path.name
        if not name or not parent.is_dir():
            return path
        want = name.lower()
        for child in parent.iterdir():
            if child.name.lower() == want:
                return child
    except Exception:
        return path
    return path


def _join_real_case(base: Path, relative: Path) -> Path:
    cur = base
    for part in relative.parts:
        cur = _real_case_path(cur / part)
    return cur


def _walk_dirs(root: Path, max_depth: int):
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
        skip = {"mods", "downloads", "overwrite", "cache", "logs", "__pycache__"}
        dirnames[:] = [d for d in dirnames if d.lower() not in skip]
        yield Path(dirpath), dirnames, filenames


def _parse_ini_hints(ini_path: Path) -> tuple[str | None, str | None, list[str]]:
    base_directory: str | None = None
    game_path_raw: str | None = None
    binaries: list[str] = []

    current_section: str | None = None
    for raw_line in ini_path.read_text(encoding="utf-8", errors="surrogateescape").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            current_section = m.group("name")
            continue
        if current_section == "Settings" and line.startswith("base_directory="):
            base_directory = line.split("=", 1)[1].strip()
        elif current_section == "General" and line.startswith("gamePath="):
            game_path_raw = line.split("=", 1)[1].strip()
        elif current_section == "customExecutables":
            m2 = _CUSTOM_BINARY_RE.match(line)
            if m2:
                binaries.append(m2.group("value"))

    game_path_str = None
    if game_path_raw:
        game_path_str = _parse_bytearray_path(game_path_raw) or game_path_raw
    return base_directory, game_path_str, binaries


def _choose_best_ini(candidates: list[Path], root: Path) -> Path | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def score(p: Path) -> tuple[int, int]:
        s = 0
        parent = p.parent
        if any((parent / exe).is_file() for exe in ("ModOrganizer.exe", "ModOrganizer64.exe")):
            s += 50
        if parent.name.lower() in {"mo2", "modorganizer", "mod organizer 2"}:
            s += 10
        if p.parent == root:
            s += 5
        depth = len(p.resolve().relative_to(root.resolve()).parts)
        return s, -depth

    return sorted(candidates, key=score, reverse=True)[0]


def _guess_instance_root(root: Path, ini_path: Path | None, base_hint: str | None) -> Path | None:
    hint_name = None
    if base_hint:
        try:
            hint_name = Path(_normalize_slashes(base_hint)).name.lower()
        except Exception:
            hint_name = None

    candidates: list[Path] = [root]
    for dirpath, dirnames, _filenames in _walk_dirs(root, max_depth=3):
        for d in list(dirnames):
            candidates.append(dirpath / d)

    best: tuple[int, int, Path] | None = None
    for cand in candidates:
        if not cand.is_dir():
            continue
        score = 0
        if (cand / "mods").is_dir():
            score += 5
        if (cand / "profiles").is_dir():
            score += 5
        if (cand / "downloads").is_dir():
            score += 2
        if (cand / "overwrite").exists():
            score += 1
        if ini_path and cand == ini_path.parent:
            score += 3
        if ini_path and cand == ini_path.parent.parent:
            score += 2
        if hint_name and cand.name.lower() == hint_name:
            score += 4

        if score < 8:
            continue
        depth = len(cand.resolve().relative_to(root.resolve()).parts)
        metric = (score, -depth, cand)
        if best is None or metric > best:
            best = metric

    if best:
        return best[2]

    if ini_path:
        return ini_path.parent
    return root


def _find_game_path(root: Path, instance_root: Path | None, old_hint: str | None, edition: str) -> Path | None:
    exe_names = {
        "sse": ("SkyrimSE.exe", "SkyrimSELauncher.exe"),
        "vr": ("SkyrimVR.exe", "SkyrimVRLauncher.exe"),
        "le": ("TESV.exe",),
    }.get(edition, ("SkyrimSE.exe",))
    main_exe = exe_names[0]
    fallback_exes = exe_names[1:]

    # 1) old hint based: .../Stock Game/<tail>
    if old_hint:
        hint_norm = _normalize_slashes(old_hint)
        parts = [p for p in hint_norm.split("/") if p]
        idx = None
        for i, seg in enumerate(parts):
            if seg.lower() in {"stock game", "stockgame", "game root", "gameroot"}:
                idx = i
                break
        if idx is not None:
            tail = Path(*parts[idx + 1 :]) if idx + 1 < len(parts) else Path()
            for base in filter(None, [instance_root, root]):
                for stock_name in (
                    "Stock Game",
                    "STOCK GAME",
                    "stock game",
                    "StockGame",
                    "STOCKGAME",
                    "stockgame",
                    "Game Root",
                    "game root",
                    "GameRoot",
                    "GAMEROOT",
                    "gameroot",
                ):
                    stock_dir = _real_case_path(base / stock_name)
                    cand = _join_real_case(stock_dir, tail) if tail.parts else stock_dir
                    if (cand / main_exe).is_file() or any((cand / exe).is_file() for exe in fallback_exes):
                        return _real_case_path(cand)

    # 2) common folder names near instance root/root
    bases = [p for p in [instance_root, root] if p]
    for base in bases:
        for stock_name in (
            "Stock Game",
            "STOCK GAME",
            "stock game",
            "StockGame",
            "STOCKGAME",
            "stockgame",
            "Game Root",
            "game root",
            "GameRoot",
            "GAMEROOT",
            "gameroot",
        ):
            d = _real_case_path(base / stock_name)
            if not d.is_dir():
                continue
            if (d / main_exe).is_file() or any((d / exe).is_file() for exe in fallback_exes):
                return d
            # one level down
            try:
                for child in d.iterdir():
                    if child.is_dir() and (
                        (child / main_exe).is_file() or any((child / exe).is_file() for exe in fallback_exes)
                    ):
                        return _real_case_path(child)
            except OSError:
                pass

    # 3) fallback: search exe (depth limited)
    def search(exes: tuple[str, ...]) -> list[Path]:
        if not exes:
            return []
        exe_lower = {e.lower() for e in exes}
        hits: list[Path] = []
        for dirpath, _dirnames, filenames in _walk_dirs(root, max_depth=5):
            for f in filenames:
                if f.lower() in exe_lower:
                    hits.append(dirpath)
                    break
        return hits

    found = search((main_exe,))
    if not found:
        found = search(fallback_exes)
    if not found:
        return None
    if len(found) == 1:
        return found[0]

    def score(p: Path) -> tuple[int, int]:
        s = 0
        p_norm = p.as_posix().lower()
        if "stock game" in p_norm or "stockgame" in p_norm:
            s += 10
        if (p / "Data").is_dir():
            s += 3
        depth = len(p.resolve().relative_to(root.resolve()).parts)
        return s, -depth

    return sorted(found, key=score, reverse=True)[0]


def _find_tool_root(root: Path, instance_root: Path | None) -> Path | None:
    candidates: list[Path] = []
    for base in filter(None, [instance_root, instance_root.parent if instance_root else None, root]):
        for name in ("tools", "Tools", "TOOLS", "TOOL", "Tool", "tool"):
            d = _real_case_path(base / name)
            if d.is_dir():
                candidates.append(d)

    # scan for any directory literally named tools/tool (depth limited)
    for dirpath, dirnames, _filenames in _walk_dirs(root, max_depth=3):
        for d in dirnames:
            if d.lower() in {"tools", "tool"}:
                candidates.append(dirpath / d)

    # de-dupe preserving order
    uniq: list[Path] = []
    seen = set()
    for c in candidates:
        try:
            r = c.resolve()
        except Exception:
            r = c
        if r in seen:
            continue
        seen.add(r)
        uniq.append(c)

    if not uniq:
        return None

    known_exes = (
        "SSEEdit.exe",
        "SSEEditQuickAutoClean.exe",
        "DynDOLODx64.exe",
        "TexGenx64.exe",
        "xLODGenx64.exe",
        "SSELODGenx64.exe",
        "Synthesis.exe",
    )
    known_lower = {e.lower() for e in known_exes}

    root_resolved = root.resolve()

    def count_hits(tool_dir: Path) -> tuple[int, int, int]:
        hits = 0
        for dirpath, _dirnames, filenames in _walk_dirs(tool_dir, max_depth=4):
            for f in filenames:
                if f.lower() in known_lower:
                    hits += 1
        try:
            depth = len(tool_dir.resolve().relative_to(root_resolved).parts)
            inside_root = 1
        except ValueError:
            depth = 999
            inside_root = 0
        return inside_root, hits, -depth

    best = sorted(uniq, key=count_hits, reverse=True)[0]
    return best


def discover_from_root(root: Path, edition: str = "sse") -> DiscoveredPaths:
    root = root.expanduser().resolve()
    warnings: list[str] = []

    if not root.is_dir():
        return DiscoveredPaths(
            root=root, ini_path=None, instance_root=None, game_path=None, tool_root=None, warnings=("root is not a directory",)
        )

    ini_candidates: list[Path] = []
    for dirpath, _dirnames, filenames in _walk_dirs(root, max_depth=3):
        for f in filenames:
            if f.lower() == "modorganizer.ini":
                ini_candidates.append(dirpath / f)

    ini_path = _choose_best_ini(ini_candidates, root)
    if ini_path is None:
        warnings.append("ModOrganizer.ini를 찾지 못했습니다(모드팩 루트를 올바르게 선택했는지 확인).")

    base_hint = None
    game_hint = None
    binaries: list[str] = []
    if ini_path:
        base_hint, game_hint, binaries = _parse_ini_hints(ini_path)
        if len(ini_candidates) > 1:
            warnings.append(
                "ModOrganizer.ini가 여러 개 발견되어 하나를 자동 선택했습니다: " + str(ini_path)
            )

    instance_root = _guess_instance_root(root, ini_path, base_hint)
    if instance_root is None:
        warnings.append("MO2 인스턴스 루트를 자동으로 찾지 못했습니다.")

    game_path = _find_game_path(root, instance_root, game_hint, edition=edition)
    if game_path is None:
        warnings.append("Stock Game(게임 루트)을 자동으로 찾지 못했습니다. (SkyrimSE.exe 탐지 실패)")

    tool_root = _find_tool_root(root, instance_root)
    if tool_root is None:
        warnings.append("tools 폴더를 자동으로 찾지 못했습니다.")

    return DiscoveredPaths(
        root=root,
        ini_path=ini_path,
        instance_root=instance_root,
        game_path=game_path,
        tool_root=tool_root,
        warnings=tuple(warnings),
    )
