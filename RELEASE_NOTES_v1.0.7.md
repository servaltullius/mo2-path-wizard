# v1.0.7 - 경로 표기 유지 및 Windows CI 복구

## 개요

이번 릴리즈는 입력한 경로의 표기를 그대로 유지하도록 고친 버전입니다.

이전 버전은 경로 자동 감지와 실행 파일 탐색 과정에서 경로를 실제 경로로 바꿔(`resolve()`) 사용했습니다. 그래서 8.3 짧은 경로(`RUNNER~1` 같은 형태)나 subst/네트워크 드라이브를 쓰는 경우, 하나의 `ModOrganizer.ini` 안에 `base_directory`와 자동 추가된 실행 파일 경로가 서로 다른 표기로 섞여 기록될 수 있었습니다.

함께 5월부터 실패하던 Windows CI를 복구해, 이번 실행 파일은 GitHub Actions의 Windows 환경에서 테스트를 통과한 뒤 빌드되었습니다.

## 변경된 점

- 경로 자동 감지와 실행 파일 탐색이 입력받은 경로 표기를 그대로 사용합니다.
  - 8.3 짧은 경로가 긴 경로로 바뀌지 않습니다.
  - subst 드라이브나 연결된 네트워크 드라이브가 실제 경로(UNC 등)로 바뀌지 않습니다.
- 패키지 `__version__`이 `0.1.0`으로 남아 있던 문제를 수정했습니다.

## 개발 관련

- 테스트가 실제 `G:\`, `D:\` 드라이브에 폴더를 만들던 문제를 수정했습니다. 모든 테스트는 임시 폴더 안에서만 동작합니다.
- GitHub Actions를 `checkout`/`setup-python`/`upload-artifact` `v7`(Node 24)로 올렸습니다.
- 버전 정보는 `src/mo2_path_wizard/__init__.py`의 `__version__` 한 곳에서 관리합니다.

## 유지되는 주요 동작

- 모드팩 폴더만 선택한 상태에서 `자동 감지 + 미리보기`를 누르면 `ModOrganizer.ini`, Stock Game, Tools 경로를 자동 감지합니다.
- `Pandora/Nemesis 자동 판단`은 기본으로 켜져 있으며, 현재 INI 상태를 보고 자동 추가/프리셋 덮어쓰기를 판단합니다.
- 현재 감지된 경로와 현재 등록된 실행 파일 목록을 미리보기 상단에 표시합니다.

## 검증 내용

- Windows CI(GitHub Actions `windows-latest`, Python 3.12)에서 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `21`개 통과
- CI에서 PyInstaller로 CLI/GUI 실행 파일을 빌드했습니다.

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`
