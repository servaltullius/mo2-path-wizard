# v1.1.0 - 옛 위치 자동 추론 · 툴 설정 파일 갱신 · MO2 실행 중 감지

## 개요

경로 패처를 단계별 구조로 다시 쓰고, 모드팩을 옮긴 뒤 남는 문제를 더 넓게 고치도록 개선한 버전입니다.

- **옛 위치 자동 추론**: INI와 툴 설정 파일에 남은 옛 경로를 보고, 모드팩이 어디서 어디로 옮겨졌는지 스스로 알아냅니다.
- **툴 설정 파일 갱신**: `ModOrganizer.ini` 말고도 DynDOLOD·BodySlide·Synthesis 등 툴 설정에 남은 옛 경로를 고칩니다.
- **MO2 실행 중 감지**: 같은 모드팩의 MO2가 켜져 있으면 적용하지 않습니다.

## 새 기능

### 옛 위치 자동 추론

옛 경로의 뒷부분(예: `mods\SKSE\Root\skse64_loader.exe`, `Stock Game\Data`)이 새 모드팩 아래에 실제로 있으면, 앞부분을 옛 모드팩 위치로 봅니다.

- `base_directory`가 없는 포터블 모드팩도 모든 경로를 옮깁니다.
- `ModOrganizer.ini`는 이미 고쳤지만 툴 설정에 옛 경로가 남은 경우에도 옛 위치를 찾습니다.
- 다음 경우는 바꾸지 않습니다.
  - 옛 폴더가 아직 있고 모드팩이 아닌 폴더(여러 모드팩이 같이 쓰는 툴 폴더 등)
  - 이름이 비슷한 다른 폴더(`D:\TAKEALOOK - Outputs`, `D:\TAKEALOOK -v2`)
  - 툴 설정에 들어 있는 다른 모드팩 경로(예: zEdit의 다른 프로필)

### 툴 설정 파일 갱신 (기본 켜짐)

| 툴 | 파일 |
|---|---|
| DynDOLOD / TexGen | `Edit Scripts\DynDOLOD\Presets\*.ini` |
| BodySlide / Outfit Studio | `CalienteTools\BodySlide\Config.xml` |
| Synthesis | `PipelineSettings.json`, `Data\<게임>\<패처>\settings.json` |
| BethINI | `BethINI.ini` |
| PGPatcher | `cfg\settings.json`, `cfg\user.json` |
| SSE-AT | `data\user\config.json` (API 키가 있어 내용은 표시하지 않음) |
| zEdit | `profiles\*\settings.json`, `profiles\*\merges.json` |
| Cathedral Assets Optimizer | `profiles\*\settings.ini` |
| Pandora | `Settings.json` |
| ESLifier | `ESLifier_Data\settings.json` |

- 파일마다 옆에 `.bak` 백업을 만듭니다.
- 툴이 실행할 때마다 다시 만드는 출력물(DynDOLOD Export, xLODGen 지형 스크립트, 로그)은 건드리지 않습니다.
- 쓰기 권한이 없거나, ANSI 인코딩 파일에 한글 경로를 써야 하는 경우는 건너뛰고 알려 줍니다.
- 끄려면 CLI `--no-external-configs`, GUI `툴 설정 파일(...)의 옛 경로도 고치기` 해제.

### MO2 실행 중 감지

MO2는 종료할 때 `ModOrganizer.ini`를 다시 써서 변경을 덮어씁니다.

- 같은 모드팩의 MO2가 실행 중이면 적용하지 않습니다. CLI는 `--force`로 무시할 수 있고, GUI는 그래도 적용할지 묻습니다.
- GUI 미리보기 맨 위에 `[MO2 실행 상태]`를 표시합니다.

### 그 밖의 추가

- `[Settings]`의 `download_directory` 등 디렉터리 경로와 `[Plugins]`에 저장된 경로를 갱신합니다. `%BASE_DIR%` 값은 그대로 둡니다.
- 적용 후에도 실행 파일이 없는 실행 항목을 알려 줍니다.
- 누락 실행 파일 자동 추가에 BodySlide/Outfit Studio, LOOT, BethINI, zEdit, SSE-AT, Dynamic Interface Patcher, Cathedral Assets Optimizer, Explore Virtual Folder, `SSEEdit64.exe`/`xEdit*.exe`, `ParallaxGen.exe`를 추가했습니다.
- 게임 에디션을 INI의 `gameName`으로 자동 판단합니다(기본값 `auto`).

## 수정

- 모드팩을 복사한 뒤 복사본의 INI를 고칠 때 옛 폴더를 계속 가리키던 문제
- 전역(AppData) 인스턴스에서 `base_directory`가 AppData 폴더로 바뀌던 문제 — 이제 인스턴스 폴더를 지정하라고 알려 줍니다.
- 여러 모드팩이 같이 쓰는 모드팩 밖의 Tools 폴더를 모드팩 TOOLS로 바꾸던 문제
- `Tool`/`TOOLS` 폴더가 함께 있을 때 엉뚱한 쪽을 고르던 문제, mods 안의 `tools`(FNIS)를 Tools 폴더로 오인하던 문제
- `Stock Game` 폴더 이름의 대소문자 차이로 게임 루트 자동 감지가 실패하던 문제
- 잘못된 게임 경로를 주면 상위 폴더 전체를 뒤져 다른 게임 설치를 고르던 문제
- 드라이브 루트(`D:/`)의 모드팩을 옮길 때 xEdit `-D:` 인자가 깨지던 문제
- UTF-8 BOM이 있는 INI, 정션/심볼릭 링크 폴더 처리
- 실제로 바꾸지 않은 값도 요약에 표시되던 문제

## 검증 내용

- 테스트를 `46`개에서 `83`개로 늘렸습니다. 독립 코드 리뷰에서 찾은 문제의 회귀 테스트도 포함합니다.
- Windows CI에서 전체 테스트가 통과한 뒤 빌드했습니다.
- 실제 모드팩 `ModOrganizer.ini`와 툴 설정 파일 복사본으로 이동 시뮬레이션을 했습니다.
  - 옛 경로가 남지 않습니다.
  - 바뀐 줄 외에는 바이트 단위로 원본과 같습니다(인코딩, 줄바꿈, BOM 유지).
  - 두 번째로 실행하면 변경 없음으로 나옵니다.
- 빌드된 실행 파일로 확인한 것:
  - 실제 Windows에서 실행 중인 MO2를 감지했습니다.
  - 실제 모드팩 dry-run에서 툴 설정 파일 12개의 옛 경로(`D:\TAKEALOOK`)를 찾았습니다(파일은 수정하지 않음).

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
486D2BCC8B988DB6BDD713A6A03B42DA84D639C6989A43D745DAAEFBC741303F  mo2-path-wizard-gui.zip
D5F02189BAF28EEF82B0530F7609C47E0029DACF7E52397E6FB3673E0249FB9D  mo2-path-wizard-gui.exe
8D202B997AB1C910939B1013C5F8D1ED4BC6F36D9CB1032467039623CB2BFD9E  mo2-path-wizard.exe
```
