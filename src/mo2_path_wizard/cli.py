from __future__ import annotations

import argparse
import json
from pathlib import Path

from .discovery import discover_from_root
from .patcher import PatchOptions, patch_modorganizer_ini


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mo2-path-wizard",
        description="MO2(Mod Organizer 2) ModOrganizer.ini 경로/Executables 자동 패처",
    )
    parser.add_argument("--root", type=Path, default=None, help="모드팩 루트 폴더(자동 탐지)")
    parser.add_argument("--ini", type=Path, default=None, help="ModOrganizer.ini 경로(직접 지정)")
    parser.add_argument(
        "--instance-root",
        type=Path,
        default=None,
        help="MO2 인스턴스(모드팩) 루트. 기본값: ini가 있는 폴더",
    )
    parser.add_argument(
        "--game-path",
        type=Path,
        default=None,
        help="Stock Game(게임 루트) 경로. 기본값: 자동 탐지/기존 값",
    )
    parser.add_argument(
        "--tool-root",
        type=Path,
        default=None,
        help="tools/Tool 폴더 경로(선택). 외부 툴 경로가 깨졌을 때 매핑에 사용",
    )
    parser.add_argument(
        "--auto-add-missing",
        action="store_true",
        help="누락된 executables(xEdit/DynDOLOD/Synthesis/Nemesis/Pandora/PGPatcher 등)을 자동으로 추가",
    )
    parser.add_argument(
        "--skip-pandora",
        action="store_true",
        help="Pandora Behaviour Engine+ 자동 추가와 arguments 프리셋 적용을 제외",
    )
    parser.add_argument(
        "--skip-nemesis",
        action="store_true",
        help="Nemesis 자동 추가를 제외",
    )
    parser.add_argument(
        "--apply-arg-presets",
        action="store_true",
        help="일부 툴(xEdit/DynDOLOD 등)에 권장 arguments 템플릿을 적용(기존 arguments를 덮어씀)",
    )
    parser.add_argument(
        "--args-json",
        type=Path,
        default=None,
        help="Executables title -> arguments 템플릿(JSON) 오버라이드. 예: {\"Edit\": \"-D:\\\"{data}\\\" -l:korean\"}",
    )
    parser.add_argument(
        "--lang",
        default="korean",
        help="xEdit 언어(-l:...). 기본: korean",
    )
    parser.add_argument(
        "--edition",
        default="sse",
        choices=["sse", "vr", "le"],
        help="게임 에디션. 기본: sse",
    )
    parser.add_argument("--dry-run", action="store_true", help="파일에 쓰지 않고 diff만 출력")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="백업(.bak) 생성을 끔(기본: 켬)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="자동 탐지 실패 시 종료(프롬프트/입력 없이)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.ini is None and args.root is None:
        raise SystemExit("Error: --root 또는 --ini 중 하나는 필수입니다.")

    discovery_warnings: list[str] = []
    if args.root is not None:
        discovered = discover_from_root(args.root, edition=args.edition)
        discovery_warnings.extend(discovered.warnings)
        if args.ini is None:
            args.ini = discovered.ini_path
        if args.instance_root is None:
            args.instance_root = discovered.instance_root
        if args.game_path is None:
            args.game_path = discovered.game_path
        if args.tool_root is None:
            args.tool_root = discovered.tool_root

    if args.ini is None:
        raise SystemExit("Error: ModOrganizer.ini를 찾지 못했습니다. --ini로 직접 지정해 주세요.")

    args_overrides: dict[str, str] = {}
    if args.args_json:
        raw = json.loads(args.args_json.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SystemExit("--args-json must be a JSON object")
        for k, v in raw.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            args_overrides[k.strip().lower()] = v

    skip_auto_add_titles: list[str] = []
    if args.skip_pandora:
        skip_auto_add_titles.append("Pandora Behaviour Engine+")
    if args.skip_nemesis:
        skip_auto_add_titles.append("Nemesis")

    options = PatchOptions(
        apply_arg_presets=args.apply_arg_presets,
        auto_add_missing=args.auto_add_missing,
        skip_auto_add_titles=tuple(skip_auto_add_titles),
        skip_arg_preset_titles=("Pandora Behaviour Engine+",) if args.skip_pandora else (),
        language=args.lang,
        edition=args.edition,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        non_interactive=args.non_interactive,
        args_overrides=args_overrides,
    )

    report = patch_modorganizer_ini(
        ini_path=args.ini,
        instance_root=args.instance_root,
        game_path=args.game_path,
        tool_root=args.tool_root,
        options=options,
    )

    if discovery_warnings:
        for w in discovery_warnings:
            print(f"[warn] {w}")

    if report.diff:
        print(report.diff)
    print(report.summary)

    return 0 if report.ok else 2
