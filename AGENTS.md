# Repository Guidelines

## Project Structure & Module Organization

- `src/mo2_path_wizard/`: core package (CLI/GUI entry points + patch logic)
  - `cli.py`: `mo2-path-wizard` CLI
  - `gui.py`: `mo2-path-wizard-gui` Tkinter GUI
  - `discovery.py`: auto-detects modpack/MO2 paths
  - `patcher.py`: rewrites `ModOrganizer.ini` + generates diffs
- `tests/`: `unittest` suite (`test_*.py`)
- `.github/workflows/`: Windows CI (runs tests, then builds via PyInstaller)
- `build/`, `dist/`: local PyInstaller outputs (ignored by `.gitignore`)

## Build, Test, and Development Commands

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .

# Run tests
python -m unittest discover -s tests -p "test*.py" -v

# Run locally (examples)
python -m mo2_path_wizard --root "D:\\Modlist" --dry-run
python -m mo2_path_wizard.gui

# Build Windows executables (PyInstaller)
powershell -ExecutionPolicy Bypass -File .\\build_windows.ps1
```

Use `--dry-run` to preview the diff. Default behavior writes changes and creates a `.bak` backup unless `--no-backup` is set.

## Coding Style & Naming Conventions

- Python 3.10+; keep dependencies minimal (the Windows build is packaged with PyInstaller).
- 4-space indentation, type hints, and `pathlib.Path` for filesystem work.
- Prefer small, pure helpers for path/INI transforms; be careful with Windows paths and Qt `@ByteArray(...)` values.

## Testing Guidelines

- Use `unittest` and `TemporaryDirectory`; tests must not require a real MO2 install or modlist.
- Name tests `test_*.py` and add regression coverage for any change to executable detection/presets (`executables.py`, `presets.py`).

## Commit & Pull Request Guidelines

- Git metadata isn’t present in this checkout; default to Conventional Commits (e.g., `feat: ...`, `fix: ...`, `test: ...`).
- PRs: describe the broken scenario, include a minimal folder layout/repro, and attach a `--dry-run` diff snippet. Include GUI screenshots for `gui.py` changes.

## Safety & Configuration Tips

- Avoid committing personal `ModOrganizer.ini` files or machine-specific absolute paths; use minimal fixtures under `tests/`.
- Recommend running with MO2 closed (running MO2 may overwrite settings on exit).


## Planning mode policy
- 모든 작업은 시작 전에 반드시 Plan Mode에서 계획을 수립한다.
- 구현/수정/실행(변경을 유발하는 작업)은 사용자가 명시적으로 "플랜 종료" 또는 "실행"을 지시한 후에만 진행한다.
- 하나의 플랜이 완료되어도 자동 전환하지 않고, 다음 작업도 기본적으로 Plan Mode에서 시작한다.
- 상위 시스템/플랫폼 정책이 강제하는 경우에는 해당 정책을 우선 적용한다.

## Experimental Features (Codex)

- Experimental toggles in `config.toml` control feature availability.
- If enabled, the agent may use these features when relevant even if not explicitly listed in this repo file.
- Usage policy still follows user request + AGENTS policy precedence.
- `use_linux_sandbox_bwrap`: prefer on Linux for safer command isolation.
- `multi_agent`: use only for independent parallel tasks (no shared state/conflicting edits).
- `apps`: use only when installed/connected; prefer explicit user intent (for example `$AppName`).

