# v1.0.6 - 자동 감지 + 미리보기 흐름 정리

## 개요

이번 릴리즈는 GUI에서 `자동 감지`와 `미리보기`를 둘 다 눌러야 하는 것처럼 보이던 혼동을 줄인 버전입니다.

기능 자체는 이미 모드팩 폴더를 기준으로 미리보기/적용 시 자동 감지를 함께 수행하고 있었기 때문에, 이번 패치는 그 실제 흐름이 화면에 바로 보이도록 버튼과 안내 문구를 정리했습니다.

## 변경된 점

- 모드팩 안내 문구를 `폴더 선택 후 바로 미리보기를 누르면 자동 감지까지 함께 실행됩니다.`로 변경했습니다.
- 기존 `자동 감지` 버튼을 `경로만 자동 감지`로 변경했습니다.
  - 고급 경로 옵션을 먼저 채워 보고 싶을 때 쓰는 보조 버튼이라는 의미를 분명히 했습니다.
- 기존 `미리보기` 버튼을 `자동 감지 + 미리보기`로 변경했습니다.
- 미리보기/적용 진행 상태 문구를 `자동 감지 + 미리보기 중...`, `자동 감지 + 적용 중...`으로 변경했습니다.
- README에 GUI 권장 흐름을 추가했습니다.

## 유지되는 주요 동작

- 모드팩 폴더만 선택한 상태에서 `자동 감지 + 미리보기`를 누르면 `ModOrganizer.ini`, Stock Game, Tools 경로를 자동 감지합니다.
- `Pandora/Nemesis 자동 판단`은 기본으로 켜져 있으며, 현재 INI 상태를 보고 자동 추가/프리셋 덮어쓰기를 판단합니다.
- Pandora가 이미 등록된 모드팩에서 Nemesis가 불필요하게 자동 추가되지 않는 v1.0.5 동작이 유지됩니다.
- 현재 감지된 경로와 현재 등록된 실행 파일 목록을 미리보기 상단에 표시합니다.

## 검증 내용

- GUI 주요 버튼/안내 문구 회귀 테스트를 추가했습니다.
- 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `21`개 통과
- GUI 모듈 문법 검사:
  - 명령: `python -m py_compile src\mo2_path_wizard\gui.py`
- PyInstaller로 CLI/GUI 실행 파일을 다시 빌드했습니다.
- 빌드된 CLI 실행 파일로 주요 옵션 노출과 실제 `G:\TAKEALOOK` dry-run을 확인했습니다.

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
B9F615398959C83EE30BAAB501F849CD1C8EF1AE0CAF5A3DE2681EB5750A272B  mo2-path-wizard-gui.zip
A97BB57FA7C790EDDF2A9D7C92BFF544C74E8B7CF090E37DC2BC930673F98AB5  mo2-path-wizard-gui.exe
2E1BC38EEC3B52B8E5BFD03C15CBF1A2F8C714BEF590E85D9BA01655969F5A1B  mo2-path-wizard.exe
```
