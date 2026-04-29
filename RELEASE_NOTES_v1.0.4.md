# v1.0.4 - 현재 실행 파일 목록 표시 및 Nemesis 제외 옵션

## 개요

이번 릴리즈는 GUI 미리보기 화면이 실제 INI 내용과 다르게 보이는 것처럼 느껴지던 문제를 개선한 버전입니다.

기존 미리보기는 변경될 부분만 diff로 보여줬기 때문에, 이미 등록되어 있지만 변경되지 않는 실행 파일 경로들은 화면에 거의 나타나지 않았습니다. 이제 미리보기 상단에서 현재 감지된 경로와 `[customExecutables]`에 실제 등록된 실행 파일 목록을 먼저 볼 수 있습니다.

## 변경된 점

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
- dry-run 출력에 안내 문구를 추가했습니다.
  - 이 화면은 전체 INI 원문이 아니라 현재 상태 요약과 변경될 diff를 보여줍니다.
  - diff에서 `-`는 현재 파일, `+`는 적용 후 내용입니다.
- 적용 예정 요약을 diff보다 먼저 보여주도록 바꿨습니다.
- 출력 영역 제목을 `현재 상태 및 변경 미리보기`로 변경했습니다.
- QSettings escape 형태의 `G:\\...` 경로를 미리보기 요약에서는 `G:/...` 형태로 읽기 좋게 표시합니다.

## 새 옵션

- CLI: `--skip-nemesis`
  - `Nemesis` 자동 추가를 제외합니다.
- GUI: `Nemesis 자동 추가 제외`
  - CLI의 `--skip-nemesis`와 같은 동작입니다.

## 유지되는 주요 수정

- Pandora 자동 추가와 arguments 프리셋 적용을 제외하는 옵션을 유지합니다.
- `HGM -> HGM2 -> HGM22`처럼 폴더명 뒤에 문자가 누적되던 경로 치환 문제 수정이 유지됩니다.
- `G:\TAKEALOOK` 구조에서 `TOOLS` 폴더를 찾지 못하던 자동감지 문제 수정이 유지됩니다.

## 검증 내용

- 실제 `G:\TAKEALOOK` 기준으로 GUI 미리보기 포맷에 현재 등록된 실행 파일 목록이 표시되는지 확인했습니다.
- `--skip-nemesis`가 Nemesis 자동 추가를 제외하는지 CLI 테스트로 확인했습니다.
- GUI 인스턴스 생성 후 즉시 종료하는 방식으로 Tkinter 런타임 오류가 없는지 확인했습니다.
- 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `17`개 통과
- PyInstaller `6.14.2`로 CLI/GUI 실행 파일을 다시 빌드했습니다.
- `mo2-path-wizard-gui.exe`를 새로 압축해 `mo2-path-wizard-gui.zip`을 갱신했습니다.

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
E4AE5B71C13B52C136A4216A58C09EE5E25059499C1FDE5FA1340831B43F0760  mo2-path-wizard-gui.zip
3AA986192BD857721BF271E8984D86D2C46F250242D76C5036B1EBE24C59F217  mo2-path-wizard-gui.exe
EC1E1B82EECB4E7075732C2F3CD7D8ABBE408B3027B018198E1A42CD6624D457  mo2-path-wizard.exe
```
