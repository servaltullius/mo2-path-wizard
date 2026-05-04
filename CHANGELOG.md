# 변경 내역

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
