# 변경 내역

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
