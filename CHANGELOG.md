# 변경 내역

## v1.1.1 - 2026-10-09

### 요약

GUI에서 고급 경로 옵션을 펼치거나 창이 작을 때 실행 버튼이 화면 밖으로 밀려나던 문제를 고친 버전입니다.

### 수정

- 고급 경로 옵션을 펼치면 왼쪽 패널 아래가 잘리고 `자동 감지 + 미리보기`/`적용` 버튼이 보이지 않던 문제
  - 설정 영역(모드팩, 실행 옵션, 고급 경로)이 스크롤됩니다. 마우스 휠을 쓸 수 있고, 스크롤바는 내용이 넘칠 때만 보입니다.
  - 미리보기/적용 버튼은 설정 영역 아래에 고정되어 항상 보입니다.
  - 고급 경로를 펼치면 그 부분으로 자동 스크롤합니다.
- 창이 좁을 때 미리보기 영역의 `지우기` 버튼이 잘리던 문제 — 이제 제목 글자가 대신 줄어듭니다.

### 검증

- Windows(4K, 배율 175%)에서 기본/최소 창 크기, 고급 경로 펼침/접힘 상태를 실제로 띄워 화면을 확인했습니다.
- 작은 창에서 고급 경로를 펼쳐도 실행 버튼이 창 안에 보이는지 확인하는 GUI 회귀 테스트를 추가했습니다(전체 `84`개 통과).

## v1.1.0 - 2026-10-09

### 요약

경로 패처를 단계별 구조로 다시 쓰고, 옛 위치 자동 추론·툴 설정 파일 갱신·MO2 실행 중 감지를 더한 전면 개선 버전입니다.

### 추가

- 옛 위치 자동 추론: INI와 툴 설정 파일에 남은 옛 경로의 뒷부분이 새 모드팩 아래에 실제로 있는지로 '어디서 어디로 옮겼는지'를 알아냅니다.
- 툴 설정 파일 갱신(기본 켜짐): DynDOLOD 프리셋, BodySlide `Config.xml`, Synthesis(`PipelineSettings.json`, 패처별 `settings.json`), BethINI, PGPatcher, SSE-AT, zEdit, CAO, Pandora, ESLifier. 파일마다 `.bak` 백업을 만듭니다. `--no-external-configs`로 끌 수 있습니다.
- MO2 실행 중 감지: 같은 모드팩의 MO2가 켜져 있으면 적용하지 않습니다(`--force`로 무시). GUI 미리보기에 `[MO2 실행 상태]`를 표시합니다.
- `[Settings]`의 `download_directory` 등 디렉터리 경로와 `[Plugins]`에 저장된 경로를 갱신합니다.
- 적용 후에도 실행 파일이 없는 실행 항목을 알려 줍니다.
- 누락 실행 파일 자동 추가 대상: BodySlide/Outfit Studio, LOOT, BethINI, zEdit, SSE-AT, DIP, CAO, Explore Virtual Folder, `SSEEdit64.exe`/`xEdit*.exe`, `ParallaxGen.exe`.
- 게임 에디션 자동 판단(`--edition auto`, 기본값): INI의 `gameName`으로 SE/VR/LE를 정합니다.

### 수정

- `base_directory`가 없는 포터블 모드팩에서 일부 경로(SKSE, Explorer++, recentDirectories 등)가 옛 위치에 남던 문제
- 모드팩을 복사한 뒤 복사본의 INI를 고칠 때 옛 폴더를 계속 가리키던 문제
- 전역(AppData) 인스턴스에서 `base_directory`가 AppData 폴더로 바뀌던 문제 — 이제 인스턴스 폴더를 지정하라고 알려 줍니다.
- 이름이 같은 `Tool`/`TOOLS` 폴더가 함께 있을 때 옛 Tools 폴더와 이름이 같은 쪽을 고릅니다. mods 안의 `tools`(예: FNIS)를 Tools 폴더로 오인하지 않습니다.
- Windows에서 `Stock Game` 폴더 이름의 대소문자 변형 때문에 게임 루트 자동 감지가 실패하던 문제
- 잘못된 게임 경로를 주면 인스턴스 상위 폴더 전체를 뒤져 다른 게임 설치를 고르던 문제 — 이제 경고만 합니다.
- UTF-8 BOM이 있는 INI의 첫 섹션을 읽지 못하던 문제
- 정션/심볼릭 링크 폴더 때문에 자동 감지가 멈추던 문제
- 실제로 바꾸지 않은 `base_directory`/`gamePath`도 요약에 표시되던 문제
- 여러 모드팩이 같이 쓰는 모드팩 밖의 Tools 폴더를 모드팩 TOOLS로 바꾸던 문제 — 옛 폴더가 남아 있고 모드팩이 아니면 그대로 둡니다.
- 드라이브 루트(`D:/`)에 있던 모드팩을 옮길 때 xEdit의 `-D:` 인자가 깨지던 문제 — 드라이브 루트는 자동으로 옮기지 않고 알려 줍니다.
- `D:\Pack -v2`처럼 모드팩 이름 뒤에 `-`로 시작하는 말이 붙은 다른 폴더까지 바뀌던 문제

### 구조

- `paths`(경로 치환), `relocate`(이동 추론), `external`(툴 설정), `mo2proc`(MO2 감지), `qtini`(Qt INI 값) 모듈로 나눴습니다.
- `patch_modorganizer_ini`를 단계별 함수로 나누고, 결과(`PatchReport`)에 이동 내역·외부 설정 변경·실행 파일 없음 항목을 담습니다.

### 검증

- 테스트 `46`개 → `83`개(이동 추론, 외부 설정, MO2 감지, 새 툴 탐지, GUI 출력, 독립 코드 리뷰에서 찾은 문제의 회귀 테스트 포함).
- 실제 모드팩 INI·툴 설정 파일 복사본으로 이동 시뮬레이션을 했습니다. 옛 경로가 남지 않고, 바뀐 줄 외에는 바이트 단위로 같으며, 두 번째 실행은 변경 없음입니다.

## v1.0.8 - 2026-10-09

### 요약

이번 릴리즈는 `ModOrganizer.ini`를 망가뜨리거나 사용자 설정을 지울 수 있던 문제들을 고친 긴급 수정 버전입니다.

### 수정

- `arguments 프리셋 적용`이 게임 실행 파일과 zEdit에 xEdit 인자를 넣던 문제를 수정했습니다.
  - 이름에 `edit`이 들어 있는지("Skyrim Special Ed**it**ion")가 아니라 실행 파일 이름으로 대상을 판정합니다.
  - `SSEEdit64.exe`, `xEdit.exe`/`xEdit64.exe`(이름을 바꾼 xEdit) 등도 인식하며, 이름을 바꾼 xEdit에는 게임 모드 플래그(`-sse`)를 함께 넣습니다.
- `arguments 프리셋 적용`이 기본으로 **비어 있는 arguments에만** 적용됩니다. 직접 넣어 둔 xEdit 플래그(`-C:`, `-B:`, `-PseudoESL` 등)나 DynDOLOD/xLODGen의 `-o:` 출력 폴더가 더 이상 지워지지 않습니다.
  - 기존 값까지 바꾸려면 CLI `--overwrite-args`, GUI `기존 arguments도 프리셋으로 덮어쓰기`를 켭니다.
- `[customExecutables]`에 `size=` 줄이 없거나 `size`보다 큰 번호의 항목이 있을 때, 누락 실행 파일 자동 추가가 기존 항목을 덮어쓰던 문제를 수정했습니다.
- 한글 등 비 ASCII 문자가 들어간 게임 경로가 `gamePath=@ByteArray(...)`에 MO2(Qt)가 읽지 못하는 형식으로 기록되던 문제를 수정했습니다. 이전 버전이 기록한 형식도 그대로 읽습니다.
- 경로 치환을 개선했습니다.
  - `D:\TAKEALOOK`를 옮길 때 이름이 비슷한 `D:\TAKEALOOK - Outputs`까지 바뀌던 문제
  - 새 위치가 옛 위치 안쪽일 때 `.../Pack/Pack/Pack/...`처럼 중복 치환되던 문제
  - `d:/old`와 `D:/Old`처럼 대소문자만 다른 경로를 놓치던 문제
- GUI에서 오류가 나면 창이 "작업 중" 상태로 멈추고 오류 메시지가 뜨지 않던 문제를 수정했습니다.
- `python -m mo2_path_wizard --root ...`가 tkinter 없는 환경에서 실행되지 않던 문제를 수정했습니다.
- xEdit/DynDOLOD VR·LE 게임 모드 플래그를 `-tes5vr`/`-tes5`로 바로잡았습니다.

### 검증

- 회귀 테스트를 추가했습니다(Qt `QSettings` 실제 출력과 비교한 `@ByteArray` 인코딩 포함). 새 회귀 테스트는 v1.0.7 코드에서 실패하는 것을 확인했습니다.
- 실제 모드팩 `ModOrganizer.ini` 복사본으로 이동 시뮬레이션을 해 기존 경로가 남지 않는 것과 두 번째 실행이 변경 없음인 것을 확인했습니다.

## v1.0.7 - 2026-10-09

### 요약

이번 릴리즈는 입력한 경로의 표기를 그대로 유지하도록 고쳐, 8.3 짧은 경로나 subst/네트워크 드라이브를 쓸 때 INI 안에 서로 다른 경로 표기가 섞이던 문제를 수정한 버전입니다. 함께 5월부터 실패하던 Windows CI를 복구했습니다.

### 수정

- 경로 자동 감지와 실행 파일 탐색이 경로를 `resolve()`로 바꾸지 않고 입력받은 표기를 그대로 사용합니다.
  - 예: `C:\Users\RUNNER~1\...`로 입력했을 때 `base_directory`는 짧은 경로, 자동 추가된 실행 파일은 `C:\Users\runneradmin\...` 긴 경로로 섞여 기록되던 문제
  - subst 드라이브나 연결된 네트워크 드라이브도 실제 경로로 바뀌지 않고 그대로 유지됩니다.
- 패키지 `__version__`이 `0.1.0`으로 남아 있던 문제를 수정했습니다. 이제 `__version__`이 유일한 버전 정보이며 `pyproject.toml`은 이를 읽어 갑니다.

### 개발

- 테스트가 실제 `G:\`, `D:\` 드라이브에 폴더를 만들던 문제를 수정했습니다. 모든 테스트는 임시 폴더 안에서만 동작합니다.
- GitHub Actions를 `checkout`/`setup-python`/`upload-artifact` `v7`(Node 24)로 올렸습니다.
- 오래된 `AGENTS.md`를 삭제했습니다.

### 검증

- Windows CI(GitHub Actions `windows-latest`, Python 3.12)에서 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `21`개 통과
- CI에서 PyInstaller로 CLI/GUI 실행 파일을 빌드했습니다.

## v1.0.6 - 2026-05-04

### 요약

이번 릴리즈는 GUI에서 `자동 감지`와 `미리보기`를 둘 다 눌러야 하는 것처럼 보이던 혼동을 줄인 버전입니다. 실제 동작처럼 모드팩 폴더 선택 후 바로 미리보기를 누르면 자동 감지까지 함께 수행된다는 흐름을 화면 문구에 반영했습니다.

### 변경

- 모드팩 안내 문구를 `폴더 선택 후 바로 미리보기를 누르면 자동 감지까지 함께 실행됩니다.`로 변경했습니다.
- 기존 `자동 감지` 버튼을 `경로만 자동 감지`로 변경했습니다.
  - 고급 경로 칸을 먼저 채워 보고 싶을 때 쓰는 보조 버튼이라는 의미를 분명히 했습니다.
- 기존 `미리보기` 버튼을 `자동 감지 + 미리보기`로 변경했습니다.
- 미리보기/적용 진행 상태 문구를 `자동 감지 + 미리보기 중...`, `자동 감지 + 적용 중...`으로 변경했습니다.
- README에 GUI 권장 흐름을 추가했습니다.

### 검증

- GUI 주요 버튼/안내 문구 회귀 테스트를 추가했습니다.
- 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `21`개 통과

## v1.0.5 - 2026-05-04

### 요약

이번 릴리즈는 사용자가 Pandora/Nemesis 제외 옵션을 일일이 체크하지 않아도 프로그램이 현재 MO2 실행 항목을 보고 자동으로 판단하도록 바꾼 버전입니다.

### 추가

- 기본 켜짐인 `Pandora/Nemesis 자동 판단` 동작을 추가했습니다.
- GUI 미리보기 상단에 `[Pandora/Nemesis 자동 판단]` 결과를 표시합니다.
- CLI에 `--no-behavior-engine-auto-detect` 옵션을 추가했습니다.
  - 특수 구성에서 자동 판단을 끄고 수동 override를 쓰고 싶을 때만 사용합니다.

### 변경

- INI에 Pandora가 이미 등록되어 있으면 Nemesis 자동 추가를 기본으로 제외합니다.
- INI에 Pandora가 이미 등록되어 있으면 `arguments 프리셋 적용`이 켜져 있어도 Pandora arguments 프리셋을 기본으로 덮어쓰지 않습니다.
- INI에 Nemesis가 이미 등록되어 있으면 Pandora 자동 추가를 기본으로 제외합니다.
- GUI의 수동 옵션 문구를 `Pandora 강제 제외`, `Nemesis 강제 제외`로 바꿔 자동 판단과 역할을 구분했습니다.

### 검증

- 실제 `G:\TAKEALOOK` 기준으로 옵션을 일일이 체크하지 않아도 다음 상태가 되는지 확인했습니다.
  - `Pandora/Nemesis 자동 판단 = True`
  - `Pandora 등록됨` 안내 표시
  - `auto-add: Nemesis` 없음
  - `changed = False`
- 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `20`개 통과

## v1.0.4 - 2026-04-29

### 요약

이번 릴리즈는 GUI 미리보기가 실제 INI 전체처럼 보이면서도 변경된 diff만 보여줘 혼동되던 문제를 개선한 버전입니다. 이제 미리보기 상단에서 현재 감지된 경로와 `[customExecutables]`에 실제 등록된 실행 파일 목록을 먼저 확인할 수 있습니다.

### 추가

- GUI 미리보기 상단에 현재 감지된 경로 요약을 추가했습니다.
  - INI 경로
  - 모드팩 루트
  - Stock Game 경로
  - Tools 경로
- GUI 미리보기 상단에 현재 등록된 실행 파일 목록을 추가했습니다.
  - 실행 항목 번호
  - title
  - binary 경로
  - workingDirectory 경로
- CLI에 `--skip-nemesis` 옵션을 추가했습니다.
- GUI에 `Nemesis 자동 추가 제외` 체크박스를 추가했습니다.
- `[customExecutables]` 현재 항목을 읽는 검사 함수를 추가했습니다.

### 변경

- GUI 출력 영역 제목을 `현재 상태 및 변경 미리보기`로 변경했습니다.
- dry-run 출력에서 적용 예정 요약을 diff보다 먼저 보여주도록 변경했습니다.
- diff 영역에 `- 는 현재 파일, + 는 적용 후 내용`이라는 안내 문구를 추가했습니다.
- QSettings escape 형태의 `G:\\...` 경로를 미리보기 요약에서는 `G:/...` 형태로 읽기 좋게 표시하도록 변경했습니다.

### 수정

- 실제 INI에는 많은 실행 파일 경로가 있는데 미리보기에는 일부 diff만 보여서, 프로그램이 실제 파일과 다르게 보여주는 것처럼 보이던 혼동을 줄였습니다.
- `recentDirectories`에 남아 있는 Nemesis 경로 흔적을 `[customExecutables]`에 등록된 실행 항목으로 오해하지 않도록 테스트로 고정했습니다.

### 검증

- 실제 `G:\TAKEALOOK` 기준으로 GUI 미리보기 포맷에 현재 등록된 실행 파일 목록이 표시되는지 확인했습니다.
- `--skip-nemesis`가 Nemesis 자동 추가를 제외하는지 CLI 테스트로 확인했습니다.
- 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `17`개 통과

## v1.0.3 - 2026-04-29

### 요약

이번 릴리즈는 기존 기능은 그대로 유지하면서 GUI를 더 보기 좋고 사용하기 편한 형태로 다듬은 버전입니다. 모드팩 선택, 실행 옵션, 고급 경로, 결과 출력 영역을 더 명확하게 나누고, 실행 상태 문구도 한국어로 정리했습니다.

### 변경

- 상단에 짙은 헤더 영역을 추가해 도구 이름과 현재 목적이 더 잘 보이도록 정리했습니다.
- 모드팩, 실행 옵션, 고급 경로, 결과 출력 영역의 시각적 구분을 강화했습니다.
- 미리보기와 적용 버튼을 더 크고 명확하게 배치했습니다.
- 결과 출력창을 어두운 콘솔 스타일로 바꾸고 diff 색상을 더 잘 보이게 조정했습니다.
- `Output`, `Ready`, `Detecting...`, `Preview complete` 등 영어 상태 문구를 한국어로 교체했습니다.
- `Options`, `Advanced Paths` 같은 섹션명을 한국어로 교체했습니다.
- 찾아보기 버튼과 경로 입력 행의 간격을 정리했습니다.

### 검증

- GUI 인스턴스 생성 후 즉시 종료하는 방식으로 Tkinter 런타임 오류가 없는지 확인했습니다.
- 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `14`개 통과

## v1.0.2 - 2026-04-29

### 요약

이번 릴리즈는 MO2 모드팩 경로 이전을 더 안전하게 만들고, 최근 Pandora 업데이트 이후 Java 기반 출력 경로가 다시 들어가는 문제를 피할 수 있게 하며, 실제 모드팩 폴더 구조에서 자동감지가 더 안정적으로 동작하도록 수정한 버전입니다.

### 추가

- CLI 사용자를 위한 `--skip-pandora` 옵션을 추가했습니다.
- GUI에 `Pandora 자동 추가/프리셋 제외` 체크박스를 추가했습니다.
- Pandora 제외 동작, 비슷한 폴더명 치환, `G:\TAKEALOOK` 형식 자동감지에 대한 회귀 테스트를 추가했습니다.

### 변경

- `--skip-pandora`가 Pandora 관련 동작 두 가지를 모두 제외하도록 변경했습니다.
  - `[customExecutables]`에 `Pandora Behaviour Engine+`가 없을 때 자동 추가하는 동작
  - 이미 존재하는 Pandora 항목에 내장 `arguments` 프리셋을 적용하는 동작
- GUI 체크박스 문구를 실제 동작에 맞게 `Pandora 자동 추가/프리셋 제외`로 정리했습니다.
- 패키지 메타데이터 버전을 `1.0.2`로 올렸습니다.

### 수정

- 사용자가 Pandora arguments를 비워도 다시 생성되던 문제를 수정했습니다.
  - 기존: `arguments 프리셋 적용(덮어쓰기)`이 켜져 있으면 기존 `Pandora Behaviour Engine+` 항목에 `--tesv:"..." -o:"...\Pandora Output"`가 다시 들어갈 수 있었습니다.
  - 변경 후: Pandora 제외 옵션이 켜져 있으면 기존 Pandora `arguments=` 줄을 그대로 둡니다.
- 앞부분이 같은 폴더 이름을 치환할 때 잘못된 경로가 만들어지는 문제를 수정했습니다.
  - 기존: `HGM`에서 `HGM2`로 옮길 때 이미 `HGM2`였던 경로가 `HGM22`가 될 수 있었습니다.
  - 기존: `HGM2`에서 `HGMT`로 옮길 때 이미 `HGM22`였던 경로가 `HGMT2`가 될 수 있었습니다.
  - 변경 후: 실제 경로 경계에서만 치환하므로 비슷한 이름의 형제 폴더는 보존됩니다.
- 모드팩 내부에 `TOOLS` 폴더가 있고 드라이브/root 쪽에도 `Tools` 폴더가 있을 때 자동감지가 실패하던 문제를 수정했습니다.
  - 실제 실패 구조: `G:\TAKEALOOK`와 `G:\Tools`가 함께 있는 환경
  - 기존: `G:\TAKEALOOK\ModOrganizer.ini`를 찾은 뒤 외부 후보 `G:\Tools` 점수 계산 중 감지가 실패할 수 있었습니다.
  - 변경 후: root 외부 도구 후보 때문에 자동감지가 중단되지 않고, 내부 `G:\TAKEALOOK\TOOLS` 폴더를 선택합니다.

### 검증

- `G:\TAKEALOOK` 자동감지 확인:
  - `ini = G:\TAKEALOOK\ModOrganizer.ini`
  - `instance = G:\TAKEALOOK`
  - `game = G:\TAKEALOOK\Stock Game`
  - `tool = G:\TAKEALOOK\TOOLS`
  - `ok = True`
  - `warnings = ()`
- 빌드된 실행 파일로 비슷한 폴더명 치환 확인:
  - `HGM -> HGM2`에서 기존 `HGM2` 경로가 보존되고 `HGM22`가 생성되지 않음
  - `HGM2 -> HGMT`에서 기존 `HGM22` 경로가 보존되고 `HGMT2`가 생성되지 않음
- 빌드된 실행 파일로 Pandora 제외 동작 확인:
  - `--skip-pandora`가 없으면 Pandora Output 프리셋이 적용됨
  - `--skip-pandora`가 있으면 Pandora arguments 프리셋이 적용되지 않음
- 전체 테스트 실행:
  - `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `14`개 통과

### 배포 파일

- `dist\mo2-path-wizard-gui.zip`
- `dist\mo2-path-wizard-gui.exe`
- `dist\mo2-path-wizard.exe`
