# v1.0.5 - Pandora/Nemesis 자동 판단

## 개요

이번 릴리즈는 사용자가 Pandora/Nemesis 제외 옵션을 일일이 체크하지 않아도, 프로그램이 현재 `ModOrganizer.ini`의 `[customExecutables]` 상태를 보고 자동으로 판단하도록 바꾼 버전입니다.

예를 들어 `G:\TAKEALOOK`처럼 Pandora가 이미 등록되어 있고 Nemesis는 등록되어 있지 않은 모드팩에서는, `누락 Executables 자동 추가`가 켜져 있어도 Nemesis를 자동 추가하지 않습니다.

## 변경된 점

- 기본 켜짐인 `Pandora/Nemesis 자동 판단` 동작을 추가했습니다.
- INI에 Pandora가 이미 등록되어 있으면 Nemesis 자동 추가를 기본으로 제외합니다.
- INI에 Pandora가 이미 등록되어 있으면 `arguments 프리셋 적용`이 켜져 있어도 Pandora arguments 프리셋을 기본으로 덮어쓰지 않습니다.
- INI에 Nemesis가 이미 등록되어 있으면 Pandora 자동 추가를 기본으로 제외합니다.
- GUI 미리보기 상단에 `[Pandora/Nemesis 자동 판단]` 결과를 표시합니다.
- GUI의 수동 옵션 문구를 `Pandora 강제 제외`, `Nemesis 강제 제외`로 바꿨습니다.

## 새 CLI 옵션

- `--no-behavior-engine-auto-detect`
  - Pandora/Nemesis 자동 판단을 끕니다.
  - 특수 구성에서 자동 판단 없이 수동 override를 쓰고 싶을 때만 사용합니다.

## 유지되는 주요 수정

- 현재 감지된 경로와 현재 등록된 실행 파일 목록을 미리보기 상단에 표시합니다.
- `HGM -> HGM2 -> HGM22`처럼 폴더명 뒤에 문자가 누적되던 경로 치환 문제 수정이 유지됩니다.
- `G:\TAKEALOOK` 구조에서 `TOOLS` 폴더를 찾지 못하던 자동감지 문제 수정이 유지됩니다.

## 검증 내용

- 실제 `G:\TAKEALOOK` 기준으로 사용자가 Pandora/Nemesis 제외 체크를 따로 하지 않아도 다음 상태가 되는지 확인했습니다.
  - `Pandora/Nemesis 자동 판단 = True`
  - `Pandora 등록됨` 안내 표시
  - `auto-add: Nemesis` 없음
  - `changed = False`
- 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `20`개 통과
- PyInstaller `6.14.2`로 CLI/GUI 실행 파일을 다시 빌드했습니다.
- `mo2-path-wizard-gui.exe`를 새로 압축해 `mo2-path-wizard-gui.zip`을 갱신했습니다.

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
0131DB5DFB44ED10B0E9B24C09563A506EB6F85F83B01917D0DEF9D5BE2DAAB6  mo2-path-wizard-gui.zip
3E8E6F499DBA0BB9DBB61B8C8296C8EBC2879BB8ABF1EFA6398C846EFAA15099  mo2-path-wizard-gui.exe
21104F48CAF7F15E4D12F8C7C0EC4882670775DF6F54D6002C61F0014935044E  mo2-path-wizard.exe
```
