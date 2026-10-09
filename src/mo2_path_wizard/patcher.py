"""ModOrganizer.ini 경로 패처.

처리 순서
1. INI 읽기(줄 단위, 원문 보존)
2. 새 위치 결정: 인스턴스 루트 / 게임 루트 / Tools 루트
3. 치환 규칙 만들기: base_directory, gamePath, Tools 추정 + 옛 경로들로부터 이동 추론(relocate)
4. INI 갱신: base_directory, gamePath, [customExecutables], [recentDirectories], [Settings] *_directory, [Plugins]
5. (옵션) 누락 실행 파일 자동 추가, arguments 프리셋
6. (옵션) 외부 툴 설정 파일 갱신
7. diff/백업/쓰기
"""

from __future__ import annotations

import difflib
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import qtini
from .executables import DEFAULT_EXECUTABLE_SPECS, ExecutableSpec, _FileIndex, locate_executable
from .external import ExternalChange, find_config_targets, plan_change, read_paths, write_change
from .paths import (
    Rule,
    apply_replacements,
    build_replacements,
    find_absolute_paths,
    normalize_slashes,
    same_path_text,
    split_segments,
    to_posix,
)
from .presets import ArgContext, arg_preset_for, edition_from_game_name
from .relocate import infer_root_moves

# 테스트/외부 코드 호환용 이름
_apply_replacements = apply_replacements
_build_replacements = build_replacements


@dataclass(frozen=True)
class PatchOptions:
    apply_arg_presets: bool = False
    # False면 arguments가 이미 있는 항목은 프리셋으로 덮어쓰지 않고 경로만 갱신한다.
    overwrite_existing_args: bool = False
    auto_add_missing: bool = False
    behavior_engine_auto_detect: bool = True
    skip_auto_add_titles: tuple[str, ...] = ()
    skip_arg_preset_titles: tuple[str, ...] = ()
    edition: str = "sse"  # "sse" | "vr" | "le" | "auto"(INI의 gameName으로 판단)
    language: str = "korean"
    dry_run: bool = False
    backup: bool = True
    non_interactive: bool = False
    args_overrides: dict[str, str] = field(default_factory=dict)
    # DynDOLOD/BodySlide/Synthesis 등 툴 설정 파일에 남은 옛 경로도 갱신
    external_configs: bool = True


@dataclass(frozen=True)
class CustomExecutableEntry:
    index: int
    title: str
    binary: str
    working_directory: str
    arguments: str


@dataclass(frozen=True)
class PatchReport:
    ok: bool
    changed: bool
    summary: str
    diff: str
    warnings: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    not_found: tuple[str, ...] = ()
    root_moves: tuple[tuple[str, str], ...] = ()  # (옛 경로, 새 경로)
    missing_binaries: tuple[CustomExecutableEntry, ...] = ()  # 적용 후에도 실행 파일이 없는 항목
    external: tuple[ExternalChange, ...] = ()
    backups: tuple[Path, ...] = ()


_SECTION_RE = re.compile(r"^﻿?\[(?P<name>[^\]]+)\]\s*$")
_CUSTOM_ENTRY_RE = re.compile(r"^(?P<idx>\d+)\\(?P<key>[^=]+)=(?P<value>.*)$")
_PANDORA_CANONICAL_TITLE = "pandora behaviour engine+"
_NEMESIS_CANONICAL_TITLE = "nemesis"
_INSTANCE_DIR_KEYS = ("download_directory", "mod_directory", "cache_directory", "profiles_directory", "overwrite_directory")


# ---------------------------------------------------------------------------
# INI 텍스트 다루기
# ---------------------------------------------------------------------------


def _read_text_preserve(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def _write_text_preserve(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8", errors="surrogateescape"))


def _strip_eol(line: str) -> str:
    return line.rstrip("\r\n")


def _line_eol(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _to_bytearray_path(path: Path) -> str:
    return qtini.encode_path_bytearray(str(path))


def _parse_bytearray_path(value: str) -> str | None:
    return qtini.decode_path_bytearray(value)


def _escape_qsettings(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class _Ini:
    """줄 목록 + 섹션 위치. 줄을 끼워 넣으면 섹션 위치를 다시 계산한다."""

    def __init__(self, text: str, newline: str) -> None:
        self.lines = text.splitlines(keepends=True)
        self.newline = newline
        self.sections: dict[str, tuple[int, int]] = {}
        self.reindex()

    def reindex(self) -> None:
        headers: list[tuple[str, int]] = []
        for i, line in enumerate(self.lines):
            m = _SECTION_RE.match(_strip_eol(line))
            if m:
                headers.append((m.group("name"), i))
        self.sections = {}
        for n, (name, start) in enumerate(headers):
            end = headers[n + 1][1] if n + 1 < len(headers) else len(self.lines)
            self.sections.setdefault(name, (start, end))

    def items(self, section: str):
        """(줄 번호, 키, 값) — 값은 원문(Qt 이스케이프 포함)."""
        if section not in self.sections:
            return
        start, end = self.sections[section]
        for i in range(start + 1, end):
            raw = _strip_eol(self.lines[i])
            if "=" not in raw or raw.lstrip().startswith((";", "#")):
                continue
            key, value = raw.split("=", 1)
            yield i, key, value

    def get(self, section: str, key: str) -> tuple[str | None, int | None]:
        for i, k, v in self.items(section):
            if k == key:
                return v, i
        return None, None

    def set_line(self, index: int, key: str, value: str) -> None:
        eol = _line_eol(self.lines[index]) or self.newline
        self.lines[index] = f"{key}={value}{eol}"

    def insert_point(self, section: str) -> int:
        """섹션 끝의 빈 줄 앞(마지막 내용 줄 바로 뒤)."""
        start, end = self.sections[section]
        i = end
        while i - 1 > start and not self.lines[i - 1].strip():
            i -= 1
        return i

    def set(self, section: str, key: str, value: str) -> bool:
        """값을 바꾸거나(섹션 안에 키가 있으면) 섹션 끝에 추가한다. 섹션이 없으면 False."""
        if section not in self.sections:
            return False
        _, idx = self.get(section, key)
        if idx is not None:
            self.set_line(idx, key, value)
        else:
            self.insert(self.insert_point(section), [f"{key}={value}"])
        return True

    def insert(self, index: int, raw_lines: list[str]) -> None:
        if index > 0 and not _line_eol(self.lines[index - 1]):
            self.lines[index - 1] += self.newline
        self.lines[index:index] = [line + self.newline for line in raw_lines]
        self.reindex()

    def append_section(self, section: str, raw_lines: list[str]) -> None:
        if self.lines and not _line_eol(self.lines[-1]):
            self.lines[-1] += self.newline
        block = [f"[{section}]"] + raw_lines
        if self.lines and self.lines[-1].strip():
            block.insert(0, "")
        self.lines.extend(line + self.newline for line in block)
        self.reindex()

    def text(self) -> str:
        return "".join(self.lines)


def _parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except Exception:
        return None


def _custom_entries(ini: _Ini) -> dict[str, dict[str, tuple[str, int]]]:
    entries: dict[str, dict[str, tuple[str, int]]] = {}
    if "customExecutables" not in ini.sections:
        return entries
    start, end = ini.sections["customExecutables"]
    for i in range(start + 1, end):
        m = _CUSTOM_ENTRY_RE.match(_strip_eol(ini.lines[i]))
        if m:
            entries.setdefault(m.group("idx"), {})[m.group("key")] = (m.group("value"), i)
    return entries


def _iter_custom_values(ini: _Ini, key: str):
    for idx, kv in _custom_entries(ini).items():
        if key in kv:
            yield idx, kv[key][0]


def inspect_custom_executables(ini_path: Path) -> tuple[CustomExecutableEntry, ...]:
    """Return current [customExecutables] entries without looking at recentDirectories."""
    if not ini_path.exists():
        return ()
    text, newline = _read_text_preserve(ini_path)
    entries = _custom_entries(_Ini(text, newline))

    out: list[CustomExecutableEntry] = []
    for idx, values in entries.items():
        parsed_idx = _parse_int(idx)
        if parsed_idx is None:
            continue
        out.append(
            CustomExecutableEntry(
                index=parsed_idx,
                title=values.get("title", ("", -1))[0].strip(),
                binary=values.get("binary", ("", -1))[0].strip(),
                working_directory=values.get("workingDirectory", ("", -1))[0].strip(),
                arguments=values.get("arguments", ("", -1))[0].strip(),
            )
        )
    return tuple(sorted(out, key=lambda entry: entry.index))


# ---------------------------------------------------------------------------
# 새 위치 결정
# ---------------------------------------------------------------------------


def _looks_like_instance(path: Path) -> bool:
    return path.is_dir() and ((path / "mods").is_dir() or (path / "profiles").is_dir())


def _resolve_instance_root(ini_path: Path, old_base_dir: str | None) -> tuple[Path | None, str | None]:
    """인스턴스 루트(=새 base_directory)를 정한다. 못 정하면 (None, 이유).

    옛 base_directory가 디스크에 아직 있어도(복사 후 수정하는 경우) INI 근처의 인스턴스를 우선한다.
    """
    ini_dir = ini_path.parent
    # INI 폴더가 곧 인스턴스(포터블 기본 구성)면 그대로 쓴다. 옛 폴더를 옆에 복사해 둔 경우에도 옛 폴더를 고르지 않는다.
    if _looks_like_instance(ini_dir):
        return ini_dir, None
    usable_old = old_base_dir if old_base_dir and "%" not in old_base_dir else None
    if usable_old:
        # 인스턴스가 INI 옆 폴더에 있는 구성(예: MO2/ModOrganizer.ini + "File Mod Skyrim SE/")
        segs = split_segments(usable_old)
        name = segs[-1] if segs else ""
        for candidate in (ini_dir / name, ini_dir.parent / name):
            if name and _looks_like_instance(candidate):
                return candidate, None
    if usable_old and Path(normalize_slashes(usable_old)).is_dir():
        return Path(normalize_slashes(usable_old)), None
    if (ini_dir / "ModOrganizer.exe").is_file():
        return ini_dir, None
    return None, (
        "MO2 인스턴스 루트(mods/profiles가 있는 폴더)를 찾지 못했습니다. "
        "전역 인스턴스라면 모드팩 폴더를 직접 지정해 주세요(--instance-root)."
    )


def _expected_game_exes(edition: str) -> tuple[str, tuple[str, ...]]:
    if edition == "vr":
        return "SkyrimVR.exe", ("SkyrimVRLauncher.exe",)
    if edition == "le":
        return "TESV.exe", ()
    return "SkyrimSE.exe", ("SkyrimSELauncher.exe",)


def _has_game_exe(path: Path, edition: str) -> bool:
    main_exe, fallback_exes = _expected_game_exes(edition)
    return (path / main_exe).is_file() or any((path / e).is_file() for e in fallback_exes)


_GAME_DIR_NAMES = ("stock game", "stockgame", "stock_game", "game root", "gameroot", "game")


def _auto_game_path(instance_root: Path, edition: str) -> Path | None:
    """인스턴스 루트(없으면 그 부모) 바로 아래 Stock Game 류 폴더에서 게임 루트를 찾는다.

    Windows에서 대소문자만 다른 이름은 같은 폴더이므로, 실제 폴더 목록을 보고 판단해 중복을 피한다.
    """
    for base in (instance_root, instance_root.parent):
        found: dict[str, Path] = {}
        try:
            children = sorted(d for d in base.iterdir() if d.is_dir())
        except OSError:
            continue
        for d in children:
            if d.name.lower() not in _GAME_DIR_NAMES:
                continue
            if _has_game_exe(d, edition):
                found.setdefault(str(d).lower(), d)
                continue
            try:
                for child in sorted(d.iterdir()):
                    if child.is_dir() and _has_game_exe(child, edition):
                        found.setdefault(str(child).lower(), child)
            except OSError:
                continue
        if len(found) == 1:
            return next(iter(found.values()))
        if found:
            return None
    return None


def _find_file_under(root: Path, filenames: tuple[str, ...], max_depth: int) -> Path | None:
    if not filenames:
        return None
    wanted = {f.lower() for f in filenames}
    for dirpath, dirnames, files in os.walk(str(root)):
        try:
            depth = len(Path(dirpath).relative_to(root).parts)
        except ValueError:
            depth = 0
        if depth >= max_depth:
            dirnames[:] = []
        dirnames.sort()
        for f in files:
            if f.lower() in wanted:
                return Path(dirpath) / f
    return None


def _normalize_game_dir(game_path: Path | None, edition: str) -> tuple[Path | None, str | None]:
    """사용자가 준 게임 경로를 실제 게임 루트(exe가 있는 폴더)로 맞춘다. 다른 폴더를 뒤지러 가지 않는다."""
    if game_path is None:
        return None, None
    main_exe, fallback_exes = _expected_game_exes(edition)
    gp = game_path.expanduser()
    if gp.is_file() and gp.suffix.lower() == ".exe":
        gp = gp.parent
    if gp.is_dir():
        if _has_game_exe(gp, edition):
            return gp, None
        # 선택한 폴더 아래에 실제 게임 루트가 더 깊게 있는 경우(예: STOCKGAME/Skyrim Special Edition/)
        found = _find_file_under(gp, (main_exe,), max_depth=3) or _find_file_under(gp, fallback_exes, max_depth=3)
        if found:
            return found.parent, None
    return None, f"게임 실행 파일({main_exe})을 찾지 못했습니다: {game_path}"


def _guess_tool_root_from_binaries(binaries: list[str]) -> str | None:
    """옛 실행 파일 경로들에서 Tools 폴더를 추정한다. mods 아래의 tools(예: FNIS)는 제외."""
    counts: Counter[str] = Counter()
    for b in binaries:
        parts = split_segments(b)
        for i, seg in enumerate(parts):
            low = seg.lower()
            if low == "mods":
                break
            if low in {"tool", "tools"}:
                counts["/".join(parts[: i + 1])] += 1
                break
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _child_dirs(base: Path) -> list[Path]:
    try:
        return [d for d in sorted(base.iterdir()) if d.is_dir()]
    except OSError:
        return []


def _find_tool_root(instance_root: Path, old_tool_root: str | None) -> Path | None:
    old_segs = split_segments(old_tool_root) if old_tool_root else []
    old_name = old_segs[-1] if old_segs else ""
    for base in (instance_root, instance_root.parent):
        try:
            dirs = [d for d in sorted(base.iterdir()) if d.is_dir() and d.name.lower() in {"tools", "tool"}]
        except OSError:
            continue
        if dirs:
            # 옛 Tools 폴더와 이름이 정확히 같은 폴더를 우선한다(Tool / TOOLS가 함께 있는 경우).
            return next((d for d in dirs if d.name == old_name), dirs[0])
    if old_tool_root:
        candidate = Path(normalize_slashes(old_tool_root))
        if candidate.is_dir():
            return candidate
    return None


def _pack_root(paths: list[Path]) -> Path | None:
    """여러 새 경로의 공통 상위 폴더(드라이브 바로 아래보다 깊을 때만)."""
    seg_lists = [split_segments(to_posix(p)) for p in paths]
    if not seg_lists:
        return None
    common = seg_lists[0]
    for segs in seg_lists[1:]:
        n = 0
        while n < len(common) and n < len(segs) and common[n].lower() == segs[n].lower():
            n += 1
        common = common[:n]
    if len(common) < 2:
        return None
    return Path("/".join(common))


# ---------------------------------------------------------------------------
# 치환 규칙
# ---------------------------------------------------------------------------


@dataclass
class _Plan:
    instance_root: Path
    game_path: Path | None
    tool_root: Path | None
    edition: str
    rules: list[Rule]
    moves: list[tuple[str, str]]
    anchors: list[Path]
    warnings: list[str]


def _collect_ini_paths(ini: _Ini, old_base_dir: str | None, old_game: str | None) -> list[str]:
    paths: list[str] = [p for p in (old_base_dir, old_game) if p and "%" not in p]
    for section in ("customExecutables", "recentDirectories", "Settings", "Plugins"):
        for _, key, value in ini.items(section):
            if section == "Settings" and not key.endswith("_directory"):
                continue
            paths.extend(find_absolute_paths(value))
    return paths


def _add_move(rules: list[Rule], moves: list[tuple[str, str]], old: str | None, new: Path | None) -> None:
    if not old or new is None or "%" in old:
        return
    new_posix = to_posix(new)
    built = build_replacements(old, new_posix)
    if not built:
        return
    old_posix = normalize_slashes(old).rstrip("/")
    if all(o.lower() != old_posix.lower() for o, _ in moves):
        moves.append((old_posix, new_posix))
    rules.extend(built)


def _add_inferred_moves(
    rules: list[Rule],
    moves: list[tuple[str, str]],
    old_paths: list[str],
    anchors: list[Path],
    warnings: list[str],
    *,
    require_name_match: bool = False,
) -> None:
    for move in infer_root_moves(old_paths, anchors, require_name_match=require_name_match):
        old_dir = Path(move.old_root)
        try:
            still_there = old_dir.is_dir()
        except OSError:
            still_there = False
        if still_there:
            # 옛 폴더가 아직 있으면 일부러 다른 곳(예: 모드팩 밖의 툴 폴더)을 쓰는 것일 수 있다.
            note = f"옛 경로가 아직 있어 그대로 둡니다: {move.old_root}"
            if note not in warnings:
                warnings.append(note)
            continue
        _add_move(rules, moves, move.old_root, move.new_root)


def _build_plan(
    ini: _Ini,
    *,
    ini_path: Path,
    instance_root: Path,
    game_path: Path | None,
    tool_root: Path | None,
    edition: str,
    old_base_dir: str | None,
    old_game: str | None,
) -> _Plan:
    warnings: list[str] = []

    # 게임 루트: 새 인스턴스 안의 Stock Game을 먼저 찾고, 없으면 기존 gamePath가 유효할 때만 유지
    if game_path is None:
        game_path = _auto_game_path(instance_root, edition)
        if game_path is None and old_game:
            candidate = Path(normalize_slashes(old_game))
            if candidate.is_dir() and _has_game_exe(candidate, edition):
                game_path = candidate
        if game_path is None:
            warnings.append("게임 루트(Stock Game)를 찾지 못해 gamePath는 바꾸지 않았습니다.")
    else:
        game_path, warn = _normalize_game_dir(game_path, edition)
        if warn:
            warnings.append(warn)

    old_tool_root = _guess_tool_root_from_binaries([v for _, v in _iter_custom_values(ini, "binary")])
    if tool_root is None:
        tool_root = _find_tool_root(instance_root, old_tool_root)

    rules: list[Rule] = []
    moves: list[tuple[str, str]] = []
    _add_move(rules, moves, old_base_dir, instance_root)
    _add_move(rules, moves, old_game, game_path)
    if old_tool_root and tool_root is not None:
        # 새 모드팩에 옛 Tools 폴더와 이름이 같은 폴더가 있으면 그쪽으로 옮긴 것으로 본다.
        tool_target = tool_root
        old_name = split_segments(old_tool_root)[-1]
        for base in (instance_root, instance_root.parent):
            same_name = [d for d in _child_dirs(base) if d.name == old_name]
            if same_name:
                tool_target = same_name[0]
                break
        _add_move(rules, moves, old_tool_root, tool_target)

    # 옛 경로들의 뒷부분이 새 모드팩 아래에 실제로 있는지로 '어디서 어디로 옮겼는지' 추론
    pack = _pack_root([p for p in (instance_root, ini_path.parent, game_path, tool_root) if p is not None])
    anchors: list[Path] = []
    for a in (instance_root, pack, tool_root):
        if a is not None and all(str(a).lower() != str(b).lower() for b in anchors):
            anchors.append(a)
    _add_inferred_moves(rules, moves, _collect_ini_paths(ini, old_base_dir, old_game), anchors, warnings)

    return _Plan(
        instance_root=instance_root,
        game_path=game_path,
        tool_root=tool_root,
        edition=edition,
        rules=rules,
        moves=moves,
        anchors=anchors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# customExecutables
# ---------------------------------------------------------------------------


def _render_args_override(title: str, template: str, ctx: ArgContext, tool_root: Path | None) -> str | None:
    values: dict[str, str] = {
        "title": title,
        "instance": str(ctx.instance_root).replace("/", "\\"),
        "mods": str(ctx.instance_root / "mods").replace("/", "\\"),
    }
    if tool_root:
        values["tools"] = str(tool_root).replace("/", "\\")
    if ctx.game_path:
        values["game"] = str(ctx.game_path).replace("/", "\\")
    if ctx.data_path:
        values["data"] = str(ctx.data_path).replace("/", "\\")

    try:
        rendered = template.format(**values)
    except (KeyError, IndexError, ValueError):
        return None
    return _escape_qsettings(rendered)


def _is_pandora_value(value: str) -> bool:
    return "pandora" in value.strip().lower()


def _is_nemesis_value(value: str) -> bool:
    return "nemesis" in value.strip().lower()


def _entry_has(kv: dict[str, tuple[str, int]], pred) -> bool:
    return pred(kv.get("title", ("", -1))[0]) or pred(kv.get("binary", ("", -1))[0])


def _title_is_skipped(title: str, skip_titles: set[str]) -> bool:
    normalized = title.strip().lower()
    if normalized in skip_titles:
        return True
    if _PANDORA_CANONICAL_TITLE in skip_titles and _is_pandora_value(normalized):
        return True
    if _NEMESIS_CANONICAL_TITLE in skip_titles and _is_nemesis_value(normalized):
        return True
    return False


def _custom_size_line(ini: _Ini) -> tuple[int | None, int]:
    """[customExecutables]의 size= 줄 위치와 값. 없으면 (None, 0)."""
    for i, key, value in ini.items("customExecutables"):
        if key == "size":
            return i, _parse_int(value) or 0
    return None, 0


def _next_free_custom_index(used: set[int], size: int) -> tuple[int, int]:
    """새 항목 번호와 갱신된 size. 이미 쓰는 번호(size보다 큰 번호 포함)는 절대 재사용하지 않는다."""
    for i in range(1, size + 1):
        if i not in used:
            return i, size
    idx = max([size, *used]) + 1
    return idx, idx


def _existing_executable_basenames(entries: dict[str, dict[str, tuple[str, int]]]) -> set[str]:
    basenames: set[str] = set()
    for kv in entries.values():
        segs = split_segments(kv.get("binary", ("", -1))[0])
        if segs:
            basenames.add(segs[-1].lower())
    return basenames


def _new_entry_lines(idx: int, spec: ExecutableSpec, binary: Path, args: str) -> list[str]:
    def b(v: bool) -> str:
        return "true" if v else "false"

    return [
        f"{idx}\\arguments={args}",
        f"{idx}\\binary={to_posix(binary)}",
        f"{idx}\\hide={b(spec.hide)}",
        f"{idx}\\ownicon={b(spec.ownicon)}",
        f"{idx}\\steamAppID={spec.steam_app_id}",
        f"{idx}\\title={spec.title}",
        f"{idx}\\toolbar={b(spec.toolbar)}",
        f"{idx}\\workingDirectory={to_posix(binary.parent)}",
    ]


@dataclass
class _ExeResult:
    added: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)


def _patch_custom_executables(ini: _Ini, plan: _Plan, options: PatchOptions) -> _ExeResult:
    result = _ExeResult()
    entries = _custom_entries(ini)
    arg_ctx = ArgContext(
        instance_root=plan.instance_root, game_path=plan.game_path, edition=plan.edition, language=options.language
    )

    skip_auto_add = {t.strip().lower() for t in options.skip_auto_add_titles}
    skip_presets = {t.strip().lower() for t in options.skip_arg_preset_titles}
    if options.behavior_engine_auto_detect:
        if any(_entry_has(kv, _is_pandora_value) for kv in entries.values()):
            skip_auto_add.add(_NEMESIS_CANONICAL_TITLE)
            skip_presets.add(_PANDORA_CANONICAL_TITLE)
        if any(_entry_has(kv, _is_nemesis_value) for kv in entries.values()):
            skip_auto_add.add(_PANDORA_CANONICAL_TITLE)

    # 1) 기존 항목 갱신 — 줄 번호가 바뀌지 않도록 새 항목 추가보다 먼저 한다.
    for idx, kv in entries.items():
        title = kv.get("title", ("", -1))[0]

        binary_changed = False
        new_bin = kv["binary"][0] if "binary" in kv else ""
        if "binary" in kv:
            old_bin, line = kv["binary"]
            new_bin = apply_replacements(old_bin, plan.rules)
            if new_bin != old_bin:
                ini.set_line(line, f"{idx}\\binary", new_bin)
                binary_changed = True

        if "workingDirectory" in kv:
            old_wd, line = kv["workingDirectory"]
            new_wd = apply_replacements(old_wd, plan.rules)
            # 비어 있으면 binary가 옮겨진 경우에만 채운다(불필요한 변경 방지)
            if not new_wd.strip() and binary_changed and new_bin.strip():
                new_wd = "/".join(normalize_slashes(new_bin).split("/")[:-1])
            if new_wd != old_wd:
                ini.set_line(line, f"{idx}\\workingDirectory", new_wd)

        if "arguments" in kv:
            old_args, line = kv["arguments"]
            new_args = apply_replacements(old_args, plan.rules)
            override_tmpl = options.args_overrides.get(title.strip().lower())
            if override_tmpl:
                override = _render_args_override(title, override_tmpl, arg_ctx, plan.tool_root)
                if override is not None:
                    new_args = override
            elif (
                options.apply_arg_presets
                and (options.overwrite_existing_args or not old_args.strip())
                and not _title_is_skipped(title, skip_presets)
            ):
                preset = arg_preset_for(title, new_bin, arg_ctx)
                if preset is not None:
                    new_args = preset
            if new_args != old_args:
                ini.set_line(line, f"{idx}\\arguments", new_args)

    # 2) 누락 실행 파일 자동 추가 — 기존 항목 뒤(섹션 끝)에만 넣는다.
    if options.auto_add_missing:
        size_line, size = _custom_size_line(ini)
        used = {int(k) for k in entries if k.isdigit()}
        existing_titles = {kv.get("title", ("", -1))[0].strip().lower() for kv in entries.values()}
        existing_basenames = _existing_executable_basenames(entries)
        index = _FileIndex()
        new_lines: list[str] = []
        for spec in DEFAULT_EXECUTABLE_SPECS:
            if _title_is_skipped(spec.title, skip_auto_add):
                continue
            if existing_basenames.intersection(n.lower() for n in spec.exe_names):
                continue
            if spec.title.strip().lower() in existing_titles:
                continue
            binary = locate_executable(spec, instance_root=plan.instance_root, tool_root=plan.tool_root, index=index)
            if not binary:
                result.not_found.append(spec.title)
                continue
            idx, size = _next_free_custom_index(used, size)
            used.add(idx)
            existing_titles.add(spec.title.strip().lower())
            existing_basenames.add(binary.name.lower())

            override_tmpl = options.args_overrides.get(spec.title.strip().lower())
            if override_tmpl:
                args = _render_args_override(spec.title, override_tmpl, arg_ctx, plan.tool_root) or ""
            else:
                args = arg_preset_for(spec.title, binary.name, arg_ctx) or ""
            new_lines.extend(_new_entry_lines(idx, spec, binary, args))
            result.added.append(spec.title)

        if result.added:
            if "customExecutables" not in ini.sections:
                ini.append_section("customExecutables", [f"size={size}"] + new_lines)
            else:
                at = ini.insert_point("customExecutables")
                if size_line is not None:
                    ini.set_line(size_line, "size", str(size))
                    ini.insert(at, new_lines)
                else:
                    ini.insert(at, [f"size={size}"] + new_lines)

    return result


_ABS_BINARY_RE = re.compile(r"^(?:[A-Za-z]:|//|\\\\)")


def _missing_binaries(ini: _Ini) -> list[CustomExecutableEntry]:
    out: list[CustomExecutableEntry] = []
    for idx, kv in _custom_entries(ini).items():
        binary = kv.get("binary", ("", -1))[0].strip()
        if not binary or not _ABS_BINARY_RE.match(binary):
            continue
        try:
            exists = Path(normalize_slashes(binary)).is_file()
        except OSError:
            exists = False
        if not exists:
            out.append(
                CustomExecutableEntry(
                    index=_parse_int(idx) or 0,
                    title=kv.get("title", ("", -1))[0].strip(),
                    binary=binary,
                    working_directory=kv.get("workingDirectory", ("", -1))[0].strip(),
                    arguments=kv.get("arguments", ("", -1))[0].strip(),
                )
            )
    return sorted(out, key=lambda e: e.index)


# ---------------------------------------------------------------------------
# 외부 툴 설정
# ---------------------------------------------------------------------------


def _plan_external(ini: _Ini, plan: _Plan) -> list[ExternalChange]:
    exes: list[Path] = [Path(normalize_slashes(b.strip())) for _, b in _iter_custom_values(ini, "binary") if b.strip()]
    index = _FileIndex()
    for spec in DEFAULT_EXECUTABLE_SPECS:
        found = locate_executable(spec, instance_root=plan.instance_root, tool_root=plan.tool_root, index=index)
        if found:
            exes.append(found)

    targets = find_config_targets(exes)
    if not targets:
        return []

    # INI는 이미 고쳐졌어도 설정 파일에는 옛 경로가 남아 있을 수 있으므로, 설정 파일 내용으로도 추론한다.
    rules = list(plan.rules)
    old_paths: list[str] = []
    for t in targets:
        old_paths.extend(read_paths(t))
    # 설정 파일에는 다른 모드팩 경로(예: zEdit의 다른 프로필)가 섞여 있을 수 있어 이름이 같은 이동만 인정한다.
    _add_inferred_moves(rules, plan.moves, old_paths, plan.anchors, plan.warnings, require_name_match=True)

    changes: list[ExternalChange] = []
    for t in targets:
        change = plan_change(t, rules)
        if change is not None:
            changes.append(change)
    return changes


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def _format_summary(
    *,
    dry_run: bool,
    ini_path: Path,
    ini_changed: bool,
    plan: _Plan,
    base_change: tuple[str, str] | None,
    game_change: tuple[str, str] | None,
    exe: _ExeResult,
    external: list[ExternalChange],
    missing: list[CustomExecutableEntry],
    warnings: list[str],
) -> str:
    lines = ["dry-run: 파일은 수정하지 않았습니다." if dry_run else "적용 완료: 변경 내용을 파일에 썼습니다."]
    lines.append(f"- ini: {ini_path}" + ("" if ini_changed else " (변경 없음)"))
    for old, new in plan.moves:
        lines.append(f"- 경로 이동: {old} -> {new}")
    if base_change:
        lines.append(f"- base_directory: {base_change[0] or '(없음)'} -> {base_change[1]}")
    if game_change:
        lines.append(f"- gamePath: {game_change[0] or '(없음)'} -> {game_change[1]}")
    if exe.added:
        lines.append(f"- auto-add: {', '.join(exe.added)}")
    if exe.not_found:
        lines.append(f"- not found: {', '.join(exe.not_found)}")
    if external:
        lines.append(f"- 외부 툴 설정: {len(external)}개 파일")
    if missing:
        lines.append(f"- 실행 파일 없음: {', '.join(e.title or str(e.index) for e in missing)}")
    for w in warnings:
        lines.append(f"- warn: {w}")
    return "\n".join(lines)


def patch_modorganizer_ini(
    *,
    ini_path: Path,
    instance_root: Path | None,
    game_path: Path | None,
    tool_root: Path | None,
    options: PatchOptions,
) -> PatchReport:
    if not ini_path.exists():
        return PatchReport(ok=False, changed=False, summary=f"INI not found: {ini_path}", diff="")

    original_text, newline = _read_text_preserve(ini_path)
    ini = _Ini(original_text, newline)

    old_base_raw, _ = ini.get("Settings", "base_directory")
    old_base_dir = qtini.unescape_string(old_base_raw) if old_base_raw is not None else None
    old_game_raw, _ = ini.get("General", "gamePath")
    old_game = None
    if old_game_raw:
        old_game = _parse_bytearray_path(old_game_raw) or qtini.unescape_string(old_game_raw)

    edition = options.edition
    if edition not in ("sse", "vr", "le"):
        game_name, _ = ini.get("General", "gameName")
        edition = edition_from_game_name(qtini.unescape_string(game_name or ""))

    if instance_root is None:
        instance_root, err = _resolve_instance_root(ini_path, old_base_dir)
        if instance_root is None:
            return PatchReport(ok=False, changed=False, summary=err or "instance root not found", diff="")

    plan = _build_plan(
        ini,
        ini_path=ini_path,
        instance_root=instance_root,
        game_path=game_path,
        tool_root=tool_root,
        edition=edition,
        old_base_dir=old_base_dir,
        old_game=old_game,
    )
    warnings = list(plan.warnings)

    # base_directory: 포터블이고 INI 폴더가 곧 인스턴스이며 원래 키가 없으면 굳이 추가하지 않는다.
    base_change: tuple[str, str] | None = None
    new_base_dir = to_posix(plan.instance_root)
    usable_old_base = old_base_dir is None or "%" not in old_base_dir
    should_set_base = bool(old_base_dir) or not same_path_text(new_base_dir, to_posix(ini_path.parent))
    if should_set_base and usable_old_base and not (old_base_dir and same_path_text(old_base_dir, new_base_dir)):
        if ini.set("Settings", "base_directory", qtini.escape_string(new_base_dir)):
            base_change = (old_base_dir or "", new_base_dir)

    game_change: tuple[str, str] | None = None
    if plan.game_path and not (old_game and same_path_text(old_game, to_posix(plan.game_path))):
        if ini.set("General", "gamePath", _to_bytearray_path(plan.game_path)):
            game_change = (old_game or "", to_posix(plan.game_path))

    exe = _patch_custom_executables(ini, plan, options)

    # [recentDirectories], [Settings] *_directory, [Plugins]: 경로 치환만
    for section, key_filter in (
        ("recentDirectories", lambda k: k.endswith("\\directory")),
        ("Settings", lambda k: k in _INSTANCE_DIR_KEYS),
        ("Plugins", lambda k: True),
    ):
        for line, key, value in list(ini.items(section)):
            if not key_filter(key):
                continue
            new_value = apply_replacements(value, plan.rules)
            if new_value != value:
                ini.set_line(line, key, new_value)

    new_text = ini.text()
    ini_changed = new_text != original_text
    external = _plan_external(ini, plan) if options.external_configs else []
    warnings = list(plan.warnings)
    missing = _missing_binaries(ini)

    report_fields = dict(
        warnings=tuple(warnings),
        added=tuple(exe.added),
        not_found=tuple(exe.not_found),
        root_moves=tuple(plan.moves),
        missing_binaries=tuple(missing),
        external=tuple(external),
    )

    if not ini_changed and not external:
        lines = ["변경 없음: 이미 경로가 올바르거나(또는 자동 탐지 실패로) 적용할 변경이 없습니다."]
        if missing:
            lines.append(f"- 실행 파일 없음: {', '.join(e.title or str(e.index) for e in missing)}")
        lines.extend(f"- warn: {w}" for w in warnings)
        return PatchReport(ok=True, changed=False, summary="\n".join(lines), diff="", **report_fields)

    diff = ""
    if ini_changed:
        diff = "".join(
            difflib.unified_diff(
                original_text.splitlines(True), new_text.splitlines(True), fromfile=str(ini_path), tofile=str(ini_path)
            )
        )

    summary = _format_summary(
        dry_run=options.dry_run,
        ini_path=ini_path,
        ini_changed=ini_changed,
        plan=plan,
        base_change=base_change,
        game_change=game_change,
        exe=exe,
        external=external,
        missing=missing,
        warnings=warnings,
    )
    if options.dry_run:
        return PatchReport(ok=True, changed=True, summary=summary, diff=diff, **report_fields)

    backups: list[Path] = []
    if ini_changed:
        if options.backup:
            bak = ini_path.with_name(ini_path.name + ".bak")
            if bak.exists():
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                bak = ini_path.with_name(ini_path.name + f".bak.{ts}")
            bak.write_bytes(original_text.encode("utf-8", errors="surrogateescape"))
            backups.append(bak)
        _write_text_preserve(ini_path, new_text)
    for change in external:
        bak = write_change(change, backup=options.backup)
        if bak:
            backups.append(bak)

    return PatchReport(ok=True, changed=True, summary=summary, diff=diff, backups=tuple(backups), **report_fields)
