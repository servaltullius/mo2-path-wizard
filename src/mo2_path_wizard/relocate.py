"""옛 절대 경로들로부터 '모드팩이 어디서 어디로 옮겨졌는지'를 추론한다.

예: `D:/TAKEALOOK/mods/SKSE/Root/skse64_loader.exe`에서 뒷부분 `mods/SKSE/Root/skse64_loader.exe`가
새 모드팩 폴더 `G:/TAKEALOOK` 아래에 실제로 있으면, 옛 루트는 `D:/TAKEALOOK`로 본다.

INI에 base_directory가 없거나(포터블), INI는 이미 고쳤지만 외부 툴 설정에 옛 경로가 남은 경우에도
같은 방식으로 옛 루트를 찾을 수 있다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .paths import is_under, join_segments, split_segments, to_posix


# 어느 모드팩에나 있는 흔한 폴더 이름은 '같은 폴더'라는 근거가 되지 못한다.
_GENERIC_NAMES = frozenset(
    {"tools", "tool", "mods", "data", "game", "stock game", "stockgame", "game root", "gameroot",
     "profiles", "downloads", "overwrite", "mo2", "modorganizer", "skyrim special edition"}
)


def _distinct_name(name: str) -> str | None:
    low = name.lower()
    return None if low in _GENERIC_NAMES else low


@dataclass(frozen=True)
class RootMove:
    old_root: str  # posix 표기
    new_root: Path
    votes: int


class _ExistsCache:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[bool, bool]] = {}

    def check(self, path: Path) -> tuple[bool, bool]:
        """(경로가 존재, 부모 폴더가 존재)."""
        key = str(path).lower()
        if key not in self._cache:
            try:
                exists = path.exists()
                parent_exists = exists or path.parent.is_dir()
            except OSError:
                exists = parent_exists = False
            self._cache[key] = (exists, parent_exists)
        return self._cache[key]


def infer_root_moves(
    old_paths: list[str], anchors: list[Path], *, min_votes: int = 2, require_name_match: bool = False
) -> list[RootMove]:
    """옛 경로 목록과 새 기준 폴더(anchors)로 '옛 루트 -> 새 기준 폴더' 이동을 추론한다.

    각 옛 경로에 대해, 앞부분(옛 루트)을 떼어 낸 뒷부분이 기준 폴더 아래에 있으면 한 표를 준다.
    - 뒷부분 전체가 존재하면 강한 증거(단, 뒷부분이 한 구간이면 폴더 이름이 같을 때만)
    - 부모 폴더만 존재하면 약한 증거(옛 루트와 기준 폴더의 이름이 같을 때만)
    폴더 이름이 같으면 한 표로도 채택하고, 다르면 min_votes 이상일 때만 채택한다.
    '이름이 같다'는 tools/mods 같은 흔한 이름이 아닐 때만 인정한다.
    require_name_match=True면 이름이 같은 경우만 채택한다(다른 모드팩 경로가 섞일 수 있는 외부 설정 파일용).
    """
    anchors = [a for a in anchors if a is not None and len(split_segments(to_posix(a))) >= 2]
    if not anchors:
        return []

    cache = _ExistsCache()
    votes: dict[tuple[str, int], int] = defaultdict(int)
    display: dict[str, str] = {}

    unique_paths: dict[str, str] = {}
    for p in old_paths:
        segs = split_segments(p)
        if len(segs) >= 2:
            unique_paths.setdefault(join_segments(segs).lower(), join_segments(segs))

    for path in unique_paths.values():
        segs = split_segments(path)
        for ai, anchor in enumerate(anchors):
            anchor_posix = to_posix(anchor)
            if is_under(path, anchor_posix):
                continue  # 이미 새 위치를 가리킨다
            anchor_name = _distinct_name(split_segments(anchor_posix)[-1])
            # 옛 루트는 최소 '드라이브 + 폴더 1개'. 뒷부분이 긴 것(앞부분이 짧은 것)부터 시도한다.
            for k in range(2, len(segs)):
                prefix, suffix = segs[:k], segs[k:]
                name_match = anchor_name is not None and _distinct_name(prefix[-1]) == anchor_name
                exists, parent_exists = cache.check(anchor.joinpath(*suffix))
                strong = exists and (len(suffix) >= 2 or name_match)
                weak = parent_exists and name_match
                if strong or weak:
                    key = join_segments(prefix).lower()
                    display.setdefault(key, join_segments(prefix))
                    votes[(key, ai)] += 1
                    break

    best: dict[str, tuple[int, int]] = {}
    for (key, ai), n in votes.items():
        if key not in best or n > best[key][1]:
            best[key] = (ai, n)

    moves: list[RootMove] = []
    for key, (ai, n) in best.items():
        anchor = anchors[ai]
        anchor_name = _distinct_name(split_segments(to_posix(anchor))[-1])
        name_match = anchor_name is not None and _distinct_name(split_segments(key)[-1]) == anchor_name
        if name_match or (n >= min_votes and not require_name_match):
            moves.append(RootMove(old_root=display[key], new_root=anchor, votes=n))
    moves.sort(key=lambda m: (-m.votes, m.old_root))
    return moves
