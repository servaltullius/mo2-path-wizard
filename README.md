# mo2-path-wizard

MO2(Mod Organizer 2) 모드팩(특히 Stock Game 구성)에서 **깨진 경로/실행 파일(Executables) 설정을 자동/반자동으로 복구**하는 Windows 전용 패처입니다.

## 하는 일

- `ModOrganizer.ini`의 `base_directory`, `gamePath`, `[customExecutables]`의 `binary/workingDirectory/arguments`에 들어있는 경로를 새 위치에 맞게 갱신
- (옵션) xEdit/DynDOLOD/xLODGen/Pandora 등 일부 툴의 **권장 arguments 템플릿**을 적용
- 적용 전 `.bak` 백업 + `--dry-run` 미리보기(diff) 지원
- GUI 미리보기에서 현재 감지된 경로와 `[customExecutables]` 실행 파일 목록 확인
- Pandora/Nemesis 실행 항목은 현재 INI 상태를 보고 자동 판단

## 사용법(개발/실행)

Python 3.10+ 환경에서:

```bash
# (추천) 모드팩 루트만 지정하면 자동 감지
python -m mo2_path_wizard --root "D:\\Modlist" --dry-run
python -m mo2_path_wizard --root "D:\\Modlist"
python -m mo2_path_wizard.gui
```

GUI에서는 모드팩 폴더를 고른 뒤 `자동 감지 + 미리보기`를 바로 누르면 됩니다.
왼쪽의 `경로만 자동 감지`는 고급 경로 칸을 먼저 채워 보고 싶을 때 쓰는 보조 버튼입니다.

### 누락된 Executables 자동 추가

`[customExecutables]`에 없으면 아래 툴들을 **찾아서 자동으로 추가**합니다(경로는 `--tool-root`/모드팩 `mods/`에서 탐지).

- xEdit(SSEEdit), DynDOLOD(TexGen/DynDOLOD), xLODGen, Synthesis
- Nemesis, Pandora, PGPatcher

```bash
python -m mo2_path_wizard --root "D:\\Modlist" --auto-add-missing --dry-run
```

Pandora/Nemesis는 기본적으로 현재 INI 상태를 보고 자동 판단합니다.

- Pandora가 이미 등록되어 있으면 Nemesis 자동 추가를 제외합니다.
- Pandora가 이미 등록되어 있으면 `arguments 프리셋 적용`이 켜져 있어도 Pandora arguments를 다시 만들지 않습니다.
- Nemesis가 이미 등록되어 있으면 Pandora 자동 추가를 제외합니다.

특수한 구성에서 자동 판단을 끄려면:

```bash
python -m mo2_path_wizard --root "D:\\Modlist" --auto-add-missing --no-behavior-engine-auto-detect --dry-run
```

Pandora를 수동으로 강제 제외하려면:

```bash
python -m mo2_path_wizard --root "D:\\Modlist" --auto-add-missing --skip-pandora --dry-run
```

Nemesis를 수동으로 강제 제외하려면:

```bash
python -m mo2_path_wizard --root "D:\\Modlist" --auto-add-missing --skip-nemesis --dry-run
```

### arguments 오버라이드(JSON)

`title -> arguments 템플릿`을 JSON으로 지정할 수 있습니다(키는 Executables의 `title`).

```json
{
  "Edit": "-D:\"{data}\" -l:korean",
  "TexGen": "-d:\"{data}\" -sse",
  "DynDOLOD": "-d:\"{data}\" -sse",
  "Pandora Behaviour Engine+": "--tesv:\"{game}\" -o:\"{mods}\\\\Pandora Output\""
}
```

```bash
python -m mo2_path_wizard --root "D:\\Modlist" --args-json ".\\args.json" --dry-run
```

## Windows 단일 exe 빌드(PyInstaller)

Windows PowerShell에서(권장: venv):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e . pyinstaller
.\build_windows.ps1
```

생성물: `dist\mo2-path-wizard-gui.exe` (또는 `dist\mo2-path-wizard.exe`)

## 주의

- MO2는 종료한 상태에서 실행하는 것을 권장합니다(실행 중이면 종료 시 설정이 다시 저장될 수 있음).
