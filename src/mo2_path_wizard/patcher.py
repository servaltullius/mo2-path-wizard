from __future__ import annotations

import difflib
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .executables import DEFAULT_EXECUTABLE_SPECS, locate_executable
from .presets import ArgContext, arg_preset_for_title


@dataclass(frozen=True)
class PatchOptions:
    apply_arg_presets: bool = False
    auto_add_missing: bool = False
    skip_auto_add_titles: tuple[str, ...] = ()
    skip_arg_preset_titles: tuple[str, ...] = ()
    edition: str = "sse"
    language: str = "korean"
    dry_run: bool = False
    backup: bool = True
    non_interactive: bool = False
    args_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PatchReport:
    ok: bool
    changed: bool
    summary: str
    diff: str


_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")
_CUSTOM_ENTRY_RE = re.compile(r"^(?P<idx>\d+)\\(?P<key>[^=]+)=(?P<value>.*)$")


def _read_text_preserve(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def _write_text_preserve(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8", errors="surrogateescape"))


def _split_lines_keepends(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _strip_eol(line: str) -> str:
    return line.rstrip("\r\n")


def _line_eol(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def _to_posix_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _to_bytearray_path(path: Path) -> str:
    win = str(path).replace("/", "\\")
    win_escaped = win.replace("\\", "\\\\")
    return f"@ByteArray({win_escaped})"


def _parse_bytearray_path(value: str) -> str | None:
    v = value.strip()
    if not (v.startswith("@ByteArray(") and v.endswith(")")):
        return None
    inner = v[len("@ByteArray(") : -1]
    return inner.replace("\\\\", "\\")


def _escape_qsettings(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_replacements(old_path: str, new_path: str) -> list[tuple[str, str]]:
    old_posix = _normalize_slashes(old_path).rstrip("/\\")
    new_posix = _normalize_slashes(new_path).rstrip("/\\")
    old_win = old_posix.replace("/", "\\")
    new_win = new_posix.replace("/", "\\")
    old_q = _escape_qsettings(old_win)
    new_q = _escape_qsettings(new_win)
    return [
        (old_q, new_q),
        (old_posix, new_posix),
        (old_win, new_win),
    ]


_PATH_REPLACEMENT_BOUNDARY_CHARS = frozenset('/\\"\'()[]{}<>,;')


def _has_path_replacement_boundary(value: str, index: int) -> bool:
    if index >= len(value):
        return True
    ch = value[index]
    return ch in _PATH_REPLACEMENT_BOUNDARY_CHARS or ch.isspace()


def _replace_path_prefix(value: str, old: str, new: str) -> str:
    if not old:
        return value

    parts: list[str] = []
    start = 0
    pos = value.find(old, start)
    while pos != -1:
        end = pos + len(old)
        if _has_path_replacement_boundary(value, end):
            parts.append(value[start:pos])
            parts.append(new)
        else:
            parts.append(value[start:end])
        start = end
        pos = value.find(old, start)

    if not parts:
        return value

    parts.append(value[start:])
    return "".join(parts)


def _apply_replacements(value: str, replacements: list[tuple[str, str]]) -> str:
    out = value
    # 긴 것부터, 그리고 경로 경계에서만 치환(HGM -> HGM2 -> HGM22 방지)
    for old, new in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
        out = _replace_path_prefix(out, old, new)
    return out


def _common_prefix_path(paths: list[str]) -> str | None:
    norms: list[str] = []
    for p in paths:
        v = _normalize_slashes(p).strip().strip('"').rstrip("/\\")
        if v:
            norms.append(v)
    if not norms:
        return None

    parts_lists: list[list[str]] = [[seg for seg in v.split("/") if seg] for v in norms]
    common = parts_lists[0]
    for parts in parts_lists[1:]:
        i = 0
        while i < len(common) and i < len(parts) and common[i].lower() == parts[i].lower():
            i += 1
        common = common[:i]
        if not common:
            return None

    # 너무 짧은 공통 경로는 위험(예: 'D:' 만)
    if len(common) < 2:
        return None

    prefix = "/".join(common)
    if norms[0].startswith("/"):
        prefix = "/" + prefix
    return prefix


def _find_section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    header_indices: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(_strip_eol(line))
        if m:
            header_indices.append((m.group("name"), i))

    ranges: dict[str, tuple[int, int]] = {}
    for idx, (name, start) in enumerate(header_indices):
        end = header_indices[idx + 1][1] if idx + 1 < len(header_indices) else len(lines)
        ranges[name] = (start, end)
    return ranges


def _get_value_in_section(
    lines: list[str], section_ranges: dict[str, tuple[int, int]], section: str, key: str
) -> tuple[str | None, int | None]:
    if section not in section_ranges:
        return None, None
    start, end = section_ranges[section]
    for i in range(start + 1, end):
        raw = _strip_eol(lines[i])
        if raw.startswith(f"{key}="):
            return raw.split("=", 1)[1], i
    return None, None


def _set_value_in_section(
    lines: list[str],
    section_ranges: dict[str, tuple[int, int]],
    section: str,
    key: str,
    value: str,
    newline: str,
) -> bool:
    start, end = section_ranges.get(section, (-1, -1))
    if start == -1:
        return False
    for i in range(start + 1, end):
        raw = _strip_eol(lines[i])
        if raw.startswith(f"{key}="):
            eol = _line_eol(lines[i]) or newline
            lines[i] = f"{key}={value}{eol}"
            return True
    insert_at = end
    lines.insert(insert_at, f"{key}={value}{newline}")
    # 섹션 범위 갱신(삽입으로 인해 후속 섹션 인덱스가 밀림)
    updated = _find_section_ranges(lines)
    section_ranges.clear()
    section_ranges.update(updated)
    return True


def _guess_tool_root_from_binaries(binaries: list[str]) -> str | None:
    counts: Counter[str] = Counter()
    for b in binaries:
        b_norm = _normalize_slashes(b)
        parts = [p for p in b_norm.split("/") if p]
        for i, seg in enumerate(parts):
            if seg.lower() in {"tool", "tools"}:
                root = "/".join(parts[: i + 1])
                counts[root] += 1
                break
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _guess_game_root_from_custom_values(
    *,
    binaries: list[str],
    working_dirs: list[str],
    edition: str,
) -> str | None:
    main_exe, fallback_exes = _expected_game_exes(edition)
    game_exes = {main_exe.lower(), *(e.lower() for e in fallback_exes)}

    stock_markers = {"stock game", "stockgame", "game root", "gameroot", "stock_game", "gameroot"}
    counts: Counter[str] = Counter()

    for wd in working_dirs:
        wd_norm = _normalize_slashes(wd).strip().strip('"')
        if not wd_norm:
            continue
        parts = [p for p in wd_norm.split("/") if p]
        if not parts:
            continue
        if any(seg.lower() in stock_markers for seg in parts):
            counts["/".join(parts)] += 10

    for b in binaries:
        b_norm = _normalize_slashes(b).strip().strip('"')
        if not b_norm:
            continue
        parts = [p for p in b_norm.split("/") if p]
        if len(parts) < 2:
            continue
        base = parts[-1]
        base_l = base.lower()
        if base_l not in game_exes:
            continue
        counts["/".join(parts[:-1])] += 5

    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _auto_game_path(instance_root: Path, edition: str) -> Path | None:
    exe_names = {
        "sse": ("SkyrimSE.exe", "SkyrimSELauncher.exe"),
        "vr": ("SkyrimVR.exe", "SkyrimVRLauncher.exe"),
        "le": ("TESV.exe",),
    }.get(edition, ("SkyrimSE.exe",))
    main_exe = exe_names[0]
    fallback_exes = exe_names[1:]

    candidate_dirs = [
        instance_root / "Stock Game",
        instance_root / "STOCK GAME",
        instance_root / "stock game",
        instance_root / "StockGame",
        instance_root / "STOCKGAME",
        instance_root / "stockgame",
        instance_root / "Game Root",
        instance_root / "GameRoot",
        instance_root / "GAMEROOT",
        instance_root / "gameroot",
        instance_root / "game",
        instance_root.parent / "Stock Game",
        instance_root.parent / "STOCK GAME",
        instance_root.parent / "stock game",
        instance_root.parent / "StockGame",
        instance_root.parent / "STOCKGAME",
        instance_root.parent / "stockgame",
        instance_root.parent / "Game Root",
        instance_root.parent / "GameRoot",
        instance_root.parent / "GAMEROOT",
        instance_root.parent / "gameroot",
        instance_root.parent / "game",
    ]

    found: list[Path] = []
    for d in candidate_dirs:
        if not d.is_dir():
            continue
        # d 자체가 게임 루트인 경우
        if (d / main_exe).is_file() or any((d / exe).is_file() for exe in fallback_exes):
            found.append(d)
            continue
        # 1단계 하위 폴더가 게임 루트인 경우(예: Stock Game/Skyrim Special Edition/)
        try:
            for child in d.iterdir():
                if child.is_dir() and (
                    (child / main_exe).is_file() or any((child / exe).is_file() for exe in fallback_exes)
                ):
                    found.append(child)
        except OSError:
            continue

    if len(found) == 1:
        return found[0]
    return None


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
    except KeyError:
        return None
    return _escape_qsettings(rendered)


def _expected_game_exes(edition: str) -> tuple[str, tuple[str, ...]]:
    if edition == "vr":
        return "SkyrimVR.exe", ("SkyrimVRLauncher.exe",)
    if edition == "le":
        return "TESV.exe", ()
    return "SkyrimSE.exe", ("SkyrimSELauncher.exe",)


def _find_file_under(root: Path, filenames: tuple[str, ...], max_depth: int) -> Path | None:
    if not filenames:
        return None
    wanted = {f.lower() for f in filenames}
    for dirpath, dirnames, files in os.walk(str(root)):
        try:
            rel = Path(dirpath).relative_to(root)
            depth = len(rel.parts)
        except Exception:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        for f in files:
            if f.lower() in wanted:
                return Path(dirpath) / f
    return None


def _normalize_game_dir(game_path: Path | None, instance_root: Path, edition: str) -> tuple[Path | None, str | None]:
    if game_path is None:
        return None, None

    gp = game_path.expanduser()
    if gp.is_file() and gp.suffix.lower() == ".exe":
        gp = gp.parent

    main_exe, fallback_exes = _expected_game_exes(edition)

    if gp.is_dir():
        if (gp / main_exe).is_file():
            return gp, None

        # 선택한 폴더 아래에 실제 게임 루트가 더 깊게 있는 경우(예: STOCKGAME/Skyrim Special Edition/)
        found = _find_file_under(gp, (main_exe,), max_depth=4)
        if found:
            return found.parent, None

        found_fb = _find_file_under(gp, fallback_exes, max_depth=4)
        if found_fb:
            if (found_fb.parent / main_exe).is_file():
                return found_fb.parent, None
            return found_fb.parent, None

    # fallback: 인스턴스 루트에서 다시 탐지
    for base in (instance_root, instance_root.parent):
        if not base or not base.is_dir():
            continue
        found = _find_file_under(base, (main_exe,), max_depth=6)
        if found:
            return found.parent, None

    return None, f"게임 실행 파일({main_exe})을 찾지 못했습니다: {game_path}"


def _parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except Exception:
        return None


def _custom_size_line(
    lines: list[str], section_ranges: dict[str, tuple[int, int]], newline: str
) -> tuple[int | None, int]:
    if "customExecutables" not in section_ranges:
        return None, 0
    s, e = section_ranges["customExecutables"]
    for i in range(s + 1, e):
        raw = _strip_eol(lines[i])
        if raw.startswith("size="):
            size = _parse_int(raw.split("=", 1)[1]) or 0
            return i, size
    # missing size= -> insert after header
    insert_at = s + 1
    lines.insert(insert_at, f"size=0{newline}")
    updated = _find_section_ranges(lines)
    section_ranges.clear()
    section_ranges.update(updated)
    return insert_at, 0


def _existing_executable_basenames(entries: dict[str, dict[str, tuple[str, int]]]) -> set[str]:
    basenames: set[str] = set()
    for kv in entries.values():
        b = kv.get("binary", ("", -1))[0]
        b_norm = _normalize_slashes(b).strip()
        if not b_norm:
            continue
        basenames.add(b_norm.split("/")[-1].lower())
    return basenames


def _next_free_custom_index(used: set[int], size: int) -> tuple[int, int]:
    for i in range(1, size + 1):
        if i not in used:
            return i, size
    return size + 1, size + 1


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
    lines = _split_lines_keepends(original_text)
    section_ranges = _find_section_ranges(lines)

    old_base_dir, _ = _get_value_in_section(lines, section_ranges, "Settings", "base_directory")
    old_game_raw, _ = _get_value_in_section(lines, section_ranges, "General", "gamePath")

    if instance_root is None:
        # Instance 모드(LocalAppData) 대비: base_directory가 실제로 존재하면 우선 사용
        if old_base_dir:
            candidate = Path(_normalize_slashes(old_base_dir))
            if candidate.is_dir():
                instance_root = candidate
        if instance_root is None:
            instance_root = ini_path.parent

    instance_root = instance_root
    new_base_dir = _to_posix_path(instance_root)

    # gamePath 결정
    old_game_path_str: str | None = None
    if old_game_raw:
        parsed = _parse_bytearray_path(old_game_raw)
        old_game_path_str = parsed or old_game_raw

    if game_path is None:
        # 기존 gamePath가 실제로 존재하면 유지(이동 안 한 경우)
        if old_game_path_str:
            candidate = Path(_normalize_slashes(old_game_path_str))
            main_exe, fallback_exes = _expected_game_exes(options.edition)
            if candidate.is_dir() and ((candidate / main_exe).is_file() or any((candidate / e).is_file() for e in fallback_exes)):
                game_path = candidate
        if game_path is None:
            game_path = _auto_game_path(instance_root, options.edition)

    game_path, game_warn = _normalize_game_dir(game_path, instance_root, options.edition)

    # 치환 룰 준비
    replacements: list[tuple[str, str]] = []
    if old_base_dir:
        replacements.extend(_build_replacements(old_base_dir, new_base_dir))

    if old_game_path_str and game_path:
        replacements.extend(_build_replacements(old_game_path_str, _to_posix_path(game_path)))

    # tools/Tool 루트 / 옛 Stock Game(게임 루트) 추정(옵션)
    binaries_for_guess: list[str] = []
    working_dirs_for_guess: list[str] = []
    if "customExecutables" in section_ranges:
        s, e = section_ranges["customExecutables"]
        for i in range(s + 1, e):
            m = _CUSTOM_ENTRY_RE.match(_strip_eol(lines[i]))
            if not m:
                continue
            if m.group("key") == "binary":
                binaries_for_guess.append(m.group("value"))
            elif m.group("key") == "workingDirectory":
                working_dirs_for_guess.append(m.group("value"))

    old_game_root_guess = _guess_game_root_from_custom_values(
        binaries=binaries_for_guess,
        working_dirs=working_dirs_for_guess,
        edition=options.edition,
    )
    if old_game_root_guess and game_path:
        replacements.extend(_build_replacements(old_game_root_guess, _to_posix_path(game_path)))

    old_tool_root = _guess_tool_root_from_binaries(binaries_for_guess)
    if tool_root is None and instance_root:
        for candidate_name in ("Tools", "tools", "Tool", "TOOLS"):
            candidate = instance_root / candidate_name
            if candidate.is_dir():
                tool_root = candidate
                break
        if tool_root is None:
            for candidate_name in ("Tools", "tools", "Tool", "TOOLS"):
                candidate = instance_root.parent / candidate_name
                if candidate.is_dir():
                    tool_root = candidate
                    break
    if tool_root is None and old_tool_root:
        candidate = Path(_normalize_slashes(old_tool_root))
        if candidate.is_dir():
            tool_root = candidate

    if old_tool_root and tool_root:
        replacements.extend(_build_replacements(old_tool_root, _to_posix_path(tool_root)))

    # 모드팩 루트 자체가 이동한 경우(예: D:\Modlist -> G:\Modlist) 대비
    old_pack_root = _common_prefix_path([p for p in [old_base_dir, old_tool_root, old_game_root_guess] if p])
    new_pack_root = _common_prefix_path(
        [p for p in [_to_posix_path(instance_root), _to_posix_path(ini_path.parent)] if p]
        + ([p for p in [_to_posix_path(game_path)] if game_path] if game_path else [])
        + ([p for p in [_to_posix_path(tool_root)] if tool_root] if tool_root else [])
    )
    if old_pack_root and new_pack_root:
        replacements.extend(_build_replacements(old_pack_root, new_pack_root))

    # base_directory 적용(포터블에서 base_directory가 없고 ini 폴더 == 인스턴스 루트인 경우에는 굳이 추가하지 않음)
    changed = False
    should_set_base_dir = bool(old_base_dir)
    if not should_set_base_dir:
        try:
            should_set_base_dir = instance_root.resolve() != ini_path.parent.resolve()
        except Exception:
            should_set_base_dir = instance_root != ini_path.parent

    if should_set_base_dir and old_base_dir != new_base_dir:
        if _set_value_in_section(lines, section_ranges, "Settings", "base_directory", new_base_dir, newline):
            changed = True

    # gamePath 적용(가능할 때)
    if game_path:
        new_game_raw = _to_bytearray_path(game_path)
        if old_game_raw and old_game_raw != new_game_raw:
            if _set_value_in_section(lines, section_ranges, "General", "gamePath", new_game_raw, newline):
                changed = True
        elif not old_game_raw:
            if _set_value_in_section(lines, section_ranges, "General", "gamePath", new_game_raw, newline):
                changed = True

    # customExecutables 패치
    added_titles: list[str] = []
    missing_titles: list[str] = []
    warnings: list[str] = []
    if game_warn:
        warnings.append(game_warn)
    if "customExecutables" in section_ranges:
        s, e = section_ranges["customExecutables"]
        entries: dict[str, dict[str, tuple[str, int]]] = {}
        for i in range(s + 1, e):
            m = _CUSTOM_ENTRY_RE.match(_strip_eol(lines[i]))
            if not m:
                continue
            idx = m.group("idx")
            key = m.group("key")
            val = m.group("value")
            entries.setdefault(idx, {})[key] = (val, i)

        arg_ctx = ArgContext(
            instance_root=instance_root,
            game_path=game_path,
            edition=options.edition,
            language=options.language,
        )

        # 누락된 executables 자동 추가
        if options.auto_add_missing:
            size_line_idx, size_val = _custom_size_line(lines, section_ranges, newline)
            # ranges가 갱신되었을 수 있으니 다시 읽기
            s, e = section_ranges["customExecutables"]

            used_indices = {int(k) for k in entries.keys() if k.isdigit()}
            existing_titles = {kv.get("title", ("", -1))[0].strip().lower() for kv in entries.values()}
            existing_basenames = _existing_executable_basenames(entries)
            skip_auto_add_titles = {title.strip().lower() for title in options.skip_auto_add_titles}

            insert_at = e
            for spec in DEFAULT_EXECUTABLE_SPECS:
                if spec.title.strip().lower() in skip_auto_add_titles:
                    continue
                exe_lower = {n.lower() for n in spec.exe_names}
                if existing_basenames.intersection(exe_lower):
                    continue
                if spec.title.strip().lower() in existing_titles:
                    continue

                binary_path = locate_executable(spec, instance_root=instance_root, tool_root=tool_root)
                if not binary_path:
                    missing_titles.append(spec.title)
                    continue

                idx, size_val = _next_free_custom_index(used_indices, size_val)
                used_indices.add(idx)
                existing_titles.add(spec.title.strip().lower())
                existing_basenames.add(binary_path.name.lower())

                title = spec.title
                title_key = title.strip().lower()

                args_val = ""
                override_tmpl = options.args_overrides.get(title_key)
                if override_tmpl:
                    override = _render_args_override(title, override_tmpl, arg_ctx, tool_root)
                    if override is not None:
                        args_val = override
                else:
                    preset = arg_preset_for_title(title, arg_ctx)
                    if preset is not None:
                        args_val = preset

                bin_str = _to_posix_path(binary_path)
                wd_str = _to_posix_path(binary_path.parent)

                def b(v: bool) -> str:
                    return "true" if v else "false"

                new_lines = [
                    f"{idx}\\arguments={args_val}{newline}",
                    f"{idx}\\binary={bin_str}{newline}",
                    f"{idx}\\hide={b(spec.hide)}{newline}",
                    f"{idx}\\ownicon={b(spec.ownicon)}{newline}",
                    f"{idx}\\steamAppID={spec.steam_app_id}{newline}",
                    f"{idx}\\title={title}{newline}",
                    f"{idx}\\toolbar={b(spec.toolbar)}{newline}",
                    f"{idx}\\workingDirectory={wd_str}{newline}",
                ]

                lines[insert_at:insert_at] = new_lines
                insert_at += len(new_lines)
                changed = True
                added_titles.append(title)

            # size 업데이트
            if size_line_idx is not None:
                eol = _line_eol(lines[size_line_idx]) or newline
                lines[size_line_idx] = f"size={size_val}{eol}"

            # 섹션 범위 갱신
            updated = _find_section_ranges(lines)
            section_ranges.clear()
            section_ranges.update(updated)
            s, e = section_ranges["customExecutables"]

        for idx, kv in entries.items():
            title = kv.get("title", ("", -1))[0]
            title_key = title.strip().lower()

            # binary 먼저 처리(workingDirectory 채우기 조건 판단용)
            binary_changed = False
            binary_val_after: str | None = None
            if "binary" in kv:
                old_bin, bin_idx = kv["binary"]
                new_bin = _apply_replacements(old_bin, replacements)
                binary_val_after = new_bin
                if new_bin != old_bin:
                    eol = _line_eol(lines[bin_idx]) or newline
                    lines[bin_idx] = f"{idx}\\binary={new_bin}{eol}"
                    changed = True
                    binary_changed = True
            else:
                binary_val_after = None

            # workingDirectory
            if "workingDirectory" in kv:
                old_wd, wd_idx = kv["workingDirectory"]
                new_wd = _apply_replacements(old_wd, replacements)

                # workingDirectory가 비어 있고, binary가 이동/치환된 경우에만 자동 채움(불필요한 변경 방지)
                if not new_wd.strip() and binary_changed and binary_val_after and binary_val_after.strip():
                    bin_norm = _normalize_slashes(binary_val_after)
                    if bin_norm.strip():
                        new_wd = "/".join(bin_norm.split("/")[:-1])

                if new_wd != old_wd:
                    eol = _line_eol(lines[wd_idx]) or newline
                    lines[wd_idx] = f"{idx}\\workingDirectory={new_wd}{eol}"
                    changed = True

            # arguments
            if "arguments" in kv:
                old_args, args_idx = kv["arguments"]
                new_args = old_args
                skip_arg_preset_titles = {title.strip().lower() for title in options.skip_arg_preset_titles}

                override_tmpl = options.args_overrides.get(title_key)
                if override_tmpl:
                    override = _render_args_override(title, override_tmpl, arg_ctx, tool_root)
                    if override is not None:
                        new_args = override
                    else:
                        new_args = _apply_replacements(new_args, replacements)
                elif options.apply_arg_presets and title_key not in skip_arg_preset_titles:
                    preset = arg_preset_for_title(title, arg_ctx)
                    if preset is not None:
                        new_args = preset
                    else:
                        new_args = _apply_replacements(new_args, replacements)
                else:
                    new_args = _apply_replacements(new_args, replacements)

                if new_args != old_args:
                    eol = _line_eol(lines[args_idx]) or newline
                    lines[args_idx] = f"{idx}\\arguments={new_args}{eol}"
                    changed = True

    # 최근 디렉터리도 같이 갱신(옵션: path 치환만)
    if "recentDirectories" in section_ranges and replacements:
        s, e = section_ranges["recentDirectories"]
        for i in range(s + 1, e):
            raw = _strip_eol(lines[i])
            if "\\directory=" not in raw:
                continue
            before = raw
            after = _apply_replacements(before, replacements)
            if after != before:
                lines[i] = after + (_line_eol(lines[i]) or newline)
                changed = True

    new_text = "".join(lines)

    if new_text == original_text:
        summary = "변경 없음: 이미 경로가 올바르거나(또는 자동 탐지 실패로) 적용할 변경이 없습니다."
        return PatchReport(ok=True, changed=False, summary=summary, diff="")

    diff = "".join(
        difflib.unified_diff(
            original_text.splitlines(True),
            new_text.splitlines(True),
            fromfile=str(ini_path),
            tofile=str(ini_path),
        )
    )

    if options.dry_run:
        summary_lines = ["dry-run: 파일은 수정하지 않았습니다."]
        if added_titles:
            summary_lines.append(f"- auto-add: {', '.join(added_titles)}")
        if missing_titles:
            summary_lines.append(f"- not found: {', '.join(missing_titles)}")
        if warnings:
            summary_lines.append(f"- warn: {', '.join(warnings)}")
        summary = "\n".join(summary_lines)
        return PatchReport(ok=True, changed=True, summary=summary, diff=diff)

    if options.backup:
        bak = ini_path.with_name(ini_path.name + ".bak")
        if bak.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            bak = ini_path.with_name(ini_path.name + f".bak.{ts}")
        bak.write_bytes(original_text.encode("utf-8", errors="surrogateescape"))

    _write_text_preserve(ini_path, new_text)

    summary_parts = [
        "적용 완료: ModOrganizer.ini 경로/Executables 설정을 갱신했습니다.",
        f"- ini: {ini_path}",
        f"- base_directory: {new_base_dir}",
    ]
    if game_path:
        summary_parts.append(f"- gamePath: {_to_posix_path(game_path)}")
    if old_tool_root and tool_root:
        summary_parts.append(f"- tool root: {old_tool_root} -> {_to_posix_path(tool_root)}")
    if added_titles:
        summary_parts.append(f"- auto-add: {', '.join(added_titles)}")
    if missing_titles:
        summary_parts.append(f"- not found: {', '.join(missing_titles)}")
    if warnings:
        summary_parts.append(f"- warn: {', '.join(warnings)}")

    return PatchReport(ok=True, changed=True, summary="\n".join(summary_parts), diff=diff)
