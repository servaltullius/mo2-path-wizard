"""경로 문자열 정규화와 '옛 경로 -> 새 경로' 치환 엔진.

INI/JSON/XML 어디에 들어 있든 같은 규칙으로 치환할 수 있도록, 규칙 하나는 세 가지 표기를 만든다.
- posix:   D:/Pack/mods
- windows: D:\\Pack\\mods
- escaped: D:\\\\Pack\\\\mods   (Qt INI 값 안의 인자, JSON 문자열)
"""

from __future__ import annotations

import re
from pathlib import Path

Rule = tuple[str, str]


def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def to_posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def to_windows(path: Path | str) -> str:
    return str(path).replace("/", "\\")


def escape_backslashes(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def split_segments(value: str) -> list[str]:
    """경로를 구간으로 나눈다. 앞쪽 `/`(POSIX)나 `//`(UNC)는 첫 구간에 붙여 보존한다."""
    norm = normalize_slashes(value.strip().strip('"'))
    lead = ""
    if norm.startswith("//"):
        lead = "//"
    elif norm.startswith("/"):
        lead = "/"
    parts = [p for p in norm.split("/") if p]
    if parts and lead:
        parts[0] = lead + parts[0]
    return parts


def join_segments(parts: list[str]) -> str:
    return "/".join(parts)


def same_path_text(a: str, b: str) -> bool:
    return [p.lower() for p in split_segments(a)] == [p.lower() for p in split_segments(b)]


def is_under(path: str, root: str) -> bool:
    p = [s.lower() for s in split_segments(path)]
    r = [s.lower() for s in split_segments(root)]
    return bool(r) and p[: len(r)] == r


def build_replacements(old_path: str, new_path: str) -> list[Rule]:
    old_posix = normalize_slashes(old_path).rstrip("/")
    new_posix = normalize_slashes(new_path).rstrip("/")
    if not old_posix or old_posix.lower() == new_posix.lower():
        return []
    # 드라이브 루트(D:/)는 규칙이 "D:"만 남아 xEdit의 -D: 같은 인자까지 바꿔 버리므로 다루지 않는다.
    if len(split_segments(old_posix)) < 2:
        return []
    old_win = old_posix.replace("/", "\\")
    new_win = new_posix.replace("/", "\\")
    return [
        (escape_backslashes(old_win), escape_backslashes(new_win)),
        (old_posix, new_posix),
        (old_win, new_win),
    ]


_BOUNDARY_CHARS = frozenset('/\\"\'()[]{}<>,;|\r\n')
# 공백 뒤가 이런 형태면 경로가 끝난 것으로 본다(다음 인자 시작). 그 외 공백은 폴더 이름의 일부일 수 있다
# (예: "D:\\TAKEALOOK - Outputs"가 "D:\\TAKEALOOK" 규칙에 걸리면 안 됨).
# "-v2\\mods"처럼 경로 구분자가 이어지면 다음 인자가 아니라 폴더 이름이다.
_ARG_AFTER_SPACE_RE = re.compile(r'[ \t]+(?:$|[\r\n]|-{1,2}[A-Za-z][^ \t"\\/]*(?=$|[ \t\r\n"]|\\")|\\?")')


def _has_end_boundary(value: str, index: int) -> bool:
    if index >= len(value):
        return True
    ch = value[index]
    if ch in _BOUNDARY_CHARS:
        return True
    if ch in " \t":
        return _ARG_AFTER_SPACE_RE.match(value, index) is not None
    return False


def _has_start_boundary(value: str, index: int) -> bool:
    if index == 0:
        return True
    prev = value[index - 1]
    return not (prev.isalnum() or prev in "/\\._~")


def apply_replacements(value: str, replacements: list[Rule]) -> str:
    """경로 경계에서만, 한 번에(single pass) 치환한다.

    - 각 위치에서 가장 긴 규칙 하나만 적용하고 치환된 결과는 다시 검사하지 않는다
      (새 경로가 옛 경로를 포함할 때 .../Pack/Pack/Pack 처럼 중복 치환되는 문제 방지).
    - Windows 경로이므로 대소문자를 구분하지 않는다.
    - 같은 옛 경로 규칙이 여러 개면 먼저 추가된 규칙이 우선한다.
    """
    rules: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for old, new in replacements:
        key = old.lower()
        if not old or key in seen:
            continue
        seen.add(key)
        rules.append((old, key, new))
    if not rules:
        return value
    rules.sort(key=lambda r: len(r[0]), reverse=True)
    first_chars = {r[1][0] for r in rules}

    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        if value[i].lower() in first_chars and _has_start_boundary(value, i):
            for old, old_l, new in rules:
                end = i + len(old)
                if value[i:end].lower() == old_l and _has_end_boundary(value, end):
                    out.append(new)
                    i = end
                    break
            else:
                out.append(value[i])
                i += 1
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


# 텍스트(INI 값, JSON, XML 등) 안의 Windows 절대 경로 후보: 드라이브 문자 또는 UNC로 시작
_ABS_PATH_RE = re.compile(r'(?<![A-Za-z0-9])(?:[A-Za-z]:|\\\\\\\\|\\\\|//)(?:\\\\|\\|/)?[^"<>|\r\n*?]*')


_LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+$")


def split_lines_keepends(text: str) -> list[str]:
    """\r\n, \n, \r에서만 줄을 나눈다(str.splitlines는 \x0c, \x85 등에서도 나눈다)."""
    return _LINE_RE.findall(text)


def find_absolute_paths(text: str) -> list[str]:
    """텍스트 안의 절대 경로 후보를 posix 표기로 뽑는다(끝의 인자/구분자는 대략 잘라낸다)."""
    found: list[str] = []
    for m in _ABS_PATH_RE.finditer(text):
        raw = m.group(0)
        # 다음 인자(` -x`, ` --x`)나 구분자(`,`, `;`) 앞에서 자른다
        raw = re.split(r'[ \t]+-{1,2}[A-Za-z]|[,;]|\\"', raw, maxsplit=1)[0]
        norm = normalize_slashes(raw.replace("\\\\", "\\")).rstrip(" /")
        if len(split_segments(norm)) >= 2:
            found.append(norm)
    return found
