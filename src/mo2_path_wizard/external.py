"""MO2 바깥 툴 설정 파일(DynDOLOD, BodySlide, Synthesis 등)에 남은 옛 절대 경로 갱신.

대상은 '툴 실행 파일 폴더 기준 상대 경로' 목록으로만 정한다. 툴이 실행할 때마다 다시 만드는
출력물(DynDOLOD Export, xLODGen LODGen_Terrain_*.txt, 로그)은 건드리지 않는다.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import Rule, apply_replacements, find_absolute_paths

# 실행 파일 이름(소문자) -> (툴 이름, 실행 파일 폴더 기준 설정 파일 패턴들, 민감 정보 포함 여부)
# 패턴의 각 구간은 대소문자를 구분하지 않으며 `*`는 임의의 한 구간이다.
_CONFIG_SPECS: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "synthesis.exe": ("Synthesis", ("PipelineSettings.json", "Data/*/*/settings.json"), False),
    "bodyslide x64.exe": ("BodySlide", ("Config.xml",), False),
    "bodyslide.exe": ("BodySlide", ("Config.xml",), False),
    "outfitstudio x64.exe": ("BodySlide", ("Config.xml",), False),
    "outfitstudio.exe": ("BodySlide", ("Config.xml",), False),
    "bethini.exe": ("BethINI", ("Bethini.ini",), False),
    "dyndolodx64.exe": ("DynDOLOD", ("Edit Scripts/DynDOLOD/Presets/*.ini",), False),
    "texgenx64.exe": ("DynDOLOD", ("Edit Scripts/DynDOLOD/Presets/*.ini",), False),
    "pgpatcher.exe": ("PGPatcher", ("cfg/settings.json", "cfg/user.json"), False),
    "parallaxgen.exe": ("PGPatcher", ("cfg/settings.json", "cfg/user.json"), False),
    "sse-at.exe": ("SSE-AT", ("data/user/config.json",), True),
    "zedit.exe": ("zEdit", ("profiles/*/settings.json", "profiles/*/merges.json"), False),
    "cathedral_assets_optimizer.exe": ("Cathedral Assets Optimizer", ("profiles/*/settings.ini",), False),
    "pandora behaviour engine+.exe": ("Pandora", ("Settings.json",), False),
    "pandora behaviour engine.exe": ("Pandora", ("Settings.json",), False),
    "eslifier.exe": ("ESLifier", ("ESLifier_Data/settings.json",), False),
}


@dataclass(frozen=True)
class ExternalTarget:
    tool: str
    path: Path
    sensitive: bool = False


@dataclass(frozen=True)
class ExternalChange:
    tool: str
    path: Path
    changed_lines: tuple[tuple[str, str], ...]  # (이전 줄, 이후 줄) — sensitive면 비어 있음
    count: int
    sensitive: bool
    new_bytes: bytes


def _ci_glob(base: Path, pattern: str) -> list[Path]:
    current = [base]
    for part in pattern.split("/"):
        nxt: list[Path] = []
        for d in current:
            try:
                children = sorted(d.iterdir())
            except OSError:
                continue
            for child in children:
                if part == "*" or (part.startswith("*.") and child.name.lower().endswith(part[1:].lower())):
                    nxt.append(child)
                elif child.name.lower() == part.lower():
                    nxt.append(child)
        current = nxt
    return [p for p in current if p.is_file()]


def find_config_targets(executables: list[Path]) -> list[ExternalTarget]:
    """실행 파일 경로 목록에서 알려진 툴의 설정 파일을 찾는다."""
    targets: dict[str, ExternalTarget] = {}
    for exe in executables:
        spec = _CONFIG_SPECS.get(exe.name.lower())
        if not spec:
            continue
        tool, patterns, sensitive = spec
        base = exe.parent
        if not base.is_dir():
            continue
        for pattern in patterns:
            for path in _ci_glob(base, pattern):
                targets.setdefault(str(path).lower(), ExternalTarget(tool=tool, path=path, sensitive=sensitive))
    return sorted(targets.values(), key=lambda t: (t.tool.lower(), str(t.path).lower()))


def _decode(raw: bytes) -> tuple[str, str, bytes]:
    """(텍스트, 인코딩, BOM)."""
    for bom, enc in ((codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")):
        if raw.startswith(bom):
            return raw[len(bom) :].decode(enc, errors="surrogateescape" if enc == "utf-8" else "replace"), enc, bom
    return raw.decode("utf-8", errors="surrogateescape"), "utf-8", b""


def _encode(text: str, encoding: str, bom: bytes) -> bytes:
    return bom + text.encode(encoding, errors="surrogateescape" if encoding == "utf-8" else "strict")


def read_paths(target: ExternalTarget) -> list[str]:
    try:
        text, _, _ = _decode(target.path.read_bytes())
    except OSError:
        return []
    return find_absolute_paths(text)


def plan_change(target: ExternalTarget, rules: list[Rule]) -> ExternalChange | None:
    try:
        raw = target.path.read_bytes()
    except OSError:
        return None
    text, encoding, bom = _decode(raw)
    old_lines = text.splitlines(keepends=True)
    new_lines = [apply_replacements(line, rules) for line in old_lines]
    if new_lines == old_lines:
        return None
    pairs = [(a.rstrip("\r\n"), b.rstrip("\r\n")) for a, b in zip(old_lines, new_lines) if a != b]
    try:
        new_bytes = _encode("".join(new_lines), encoding, bom)
    except UnicodeEncodeError:
        return None
    return ExternalChange(
        tool=target.tool,
        path=target.path,
        changed_lines=() if target.sensitive else tuple(pairs),
        count=len(pairs),
        sensitive=target.sensitive,
        new_bytes=new_bytes,
    )


def write_change(change: ExternalChange, *, backup: bool) -> Path | None:
    """변경을 쓰고 백업 경로를 돌려준다."""
    bak: Path | None = None
    if backup:
        bak = change.path.with_name(change.path.name + ".bak")
        if bak.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            bak = change.path.with_name(change.path.name + f".bak.{ts}")
        bak.write_bytes(change.path.read_bytes())
    change.path.write_bytes(change.new_bytes)
    return bak


def describe_changes(changes: list[ExternalChange] | tuple[ExternalChange, ...], *, max_lines: int = 3) -> str:
    """사람이 읽을 외부 설정 변경 목록. 민감한 파일(API 키 등)은 줄 내용을 보여 주지 않는다."""
    out: list[str] = []
    for c in changes:
        out.append(f"- [{c.tool}] {c.path} ({c.count}줄)")
        if c.sensitive:
            out.append("    (API 키 등 민감한 정보가 있는 파일이라 내용은 표시하지 않습니다)")
            continue
        for before, after in c.changed_lines[:max_lines]:
            out.append(f"    - {before.strip()}")
            out.append(f"    + {after.strip()}")
        if c.count > max_lines:
            out.append(f"    ... 외 {c.count - max_lines}줄")
    return "\n".join(out)
