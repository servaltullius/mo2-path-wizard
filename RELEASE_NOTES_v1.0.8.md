# v1.0.8 - INI 손상·설정 덮어쓰기 긴급 수정

## 개요

이번 릴리즈는 `ModOrganizer.ini`를 망가뜨리거나 사용자가 직접 넣은 설정을 지울 수 있던 문제들을 고친 긴급 수정 버전입니다. 실제 모드팩 INI 복사본으로 이동 시뮬레이션을 하며 찾은 문제들입니다.

## 꼭 확인해 주세요

이전 버전에서 `arguments 프리셋 적용`을 켜고 실행한 적이 있다면, 아래 항목의 arguments에 xEdit용 인자(`-D:"...\Data" -l:korean`)가 잘못 들어가 있을 수 있습니다.

- `Skyrim Special Edition` (SkyrimSE.exe)
- `Skyrim Special Edition Launcher`
- `zEdit`

이번 버전은 이미 잘못 들어간 값을 자동으로 지우지 않습니다. MO2의 실행 파일 편집 창에서 해당 항목의 인자 칸을 비워 주세요. 같은 실행에서 덮어써진 xEdit 플래그나 DynDOLOD/xLODGen의 `-o:` 출력 폴더는, 실행 전에 만들어진 `ModOrganizer.ini.bak`에서 확인할 수 있습니다.

## 변경된 점

- `arguments 프리셋 적용`의 대상을 **실행 파일 이름**으로 판정합니다.
  - 게임 실행 파일(SkyrimSE.exe, Launcher, SKSE)과 zEdit에는 적용하지 않습니다.
  - `SSEEdit64.exe`, `xEdit.exe`, `xEdit64.exe`도 xEdit으로 인식합니다. 이름을 바꾼 xEdit에는 게임 모드 플래그(`-sse`)를 함께 넣습니다.
- `arguments 프리셋 적용`은 기본으로 **arguments가 비어 있는 항목에만** 적용됩니다.
  - 이미 있는 arguments까지 바꾸려면 CLI `--overwrite-args`, GUI `기존 arguments도 프리셋으로 덮어쓰기`를 켭니다.
- 누락 실행 파일 자동 추가가 기존 항목을 덮어쓰지 않습니다.
  - `[customExecutables]`에 `size=` 줄이 없는 경우
  - `size`보다 큰 번호의 항목이 이미 있는 경우
- 한글 등이 들어간 게임 경로를 MO2(Qt)가 읽는 `@ByteArray` 형식 그대로 기록합니다. 이전 버전이 기록한 형식도 읽을 수 있습니다.
- 경로 치환을 개선했습니다.
  - 이름이 비슷한 폴더(`D:\TAKEALOOK`와 `D:\TAKEALOOK - Outputs`)를 구분합니다.
  - 새 위치가 옛 위치 안쪽일 때 경로가 중복 치환되지 않습니다.
  - 대소문자만 다른 경로(`d:/old`, `D:/Old`)도 같은 경로로 봅니다.
- GUI에서 오류가 나면 창이 "작업 중"으로 멈추던 문제를 고쳤습니다. 이제 오류 메시지가 표시됩니다.
- CLI가 tkinter 없는 환경에서도 실행됩니다.
- xEdit/DynDOLOD의 VR·LE 게임 모드 플래그를 `-tes5vr`/`-tes5`로 바로잡았습니다.

## 다음 버전 예고 (v1.1.0)

- `download_directory` 등 디렉터리 경로, `base_directory`가 없는 포터블 모드팩의 경로 추정
- MO2 실행 중 감지
- 최신 툴 목록(BodySlide, LOOT, BethINI, SSE-AT 등)
- DynDOLOD, BodySlide, Synthesis 등 외부 툴 설정 파일의 경로 갱신

## 검증 내용

- 회귀 테스트를 추가했습니다. `@ByteArray` 인코딩은 Qt `QSettings`가 실제로 기록한 결과와 비교합니다.
- 새 회귀 테스트가 v1.0.7 코드에서는 실패하는 것을 확인했습니다.
- 실제 모드팩 `ModOrganizer.ini` 복사본으로 이동 시뮬레이션을 했습니다.
  - 옛 경로가 남지 않습니다.
  - 줄 수, CRLF, 키 순서가 유지됩니다.
  - 같은 INI에 두 번째로 실행하면 변경 없음으로 나옵니다.
