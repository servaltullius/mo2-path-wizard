# v1.0.2 - Pandora 제외, 안전한 경로 치환, 자동감지 수정

## 개요

이번 릴리즈는 Pandora 업데이트 이후 실제 모드팩 테스트 중 확인된 문제와, 복사한 모드팩 폴더 이름을 바꿔가며 테스트할 때 발생한 경로 치환 문제를 수정한 버전입니다.

`HGM`, `HGM2`, `HGMT`, `TAKEALOOK`처럼 모드팩을 복사하거나 이름을 바꿔서 테스트하는 환경에서는 이 버전을 사용하는 것을 권장합니다.

## 수정된 문제

- Pandora arguments가 사용자가 지운 뒤에도 다시 생성되던 문제를 수정했습니다.
  - 기존 동작: `arguments 프리셋 적용(덮어쓰기)`이 켜져 있으면 기존 `Pandora Behaviour Engine+` 항목에 `--tesv:"..." -o:"...\Pandora Output"` 인자가 다시 들어갈 수 있었습니다.
  - 변경 후: `--skip-pandora` 또는 `Pandora 자동 추가/프리셋 제외` 옵션을 켜면 기존 Pandora `arguments=` 줄을 건드리지 않습니다.
- 폴더 이름이 서로 앞부분을 공유할 때 경로가 잘못 치환되던 문제를 수정했습니다.
  - 기존 동작: `HGM -> HGM2` 변경 시 이미 `HGM2`였던 경로가 `HGM22`로 바뀔 수 있었습니다.
  - 기존 동작: `HGM2 -> HGMT` 변경 시 이미 `HGM22`였던 경로가 `HGMT2`로 바뀔 수 있었습니다.
  - 변경 후: 실제 경로 경계에서만 치환하므로, 비슷한 이름의 형제 폴더는 그대로 유지됩니다.
- `G:\TAKEALOOK` 구조에서 자동감지가 실패하던 문제를 수정했습니다.
  - 기존 동작: `G:\TAKEALOOK\ModOrganizer.ini`는 찾았지만, 외부 후보인 `G:\Tools`를 점수 계산하는 과정에서 감지가 실패할 수 있었습니다.
  - 변경 후: `G:\TAKEALOOK\TOOLS`를 정상 선택하고 경고 없이 자동감지가 완료됩니다.

## 새 옵션 및 변경된 옵션

- CLI: `--skip-pandora`
  - `Pandora Behaviour Engine+` 자동 추가를 건너뜁니다.
  - 이미 존재하는 Pandora 항목에도 내장 arguments 프리셋을 적용하지 않습니다.
- GUI: `Pandora 자동 추가/프리셋 제외`
  - CLI의 `--skip-pandora`와 같은 동작입니다.

## 검증 내용

- 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `14`개 통과
- 실제 `G:\TAKEALOOK` 자동감지 확인:
  - `ini = G:\TAKEALOOK\ModOrganizer.ini`
  - `instance = G:\TAKEALOOK`
  - `game = G:\TAKEALOOK\Stock Game`
  - `tool = G:\TAKEALOOK\TOOLS`
  - `ok = True`
  - `warnings = ()`
- 빌드된 실행 파일로 dry-run 확인:
  - `.\dist\mo2-path-wizard.exe --root 'G:\TAKEALOOK' --dry-run --skip-pandora`
  - 결과: 자동감지 중단 없음
- 빌드된 실행 파일로 폴더명 prefix 문제 확인:
  - `HGM -> HGM2`에서 `HGM22`가 새로 만들어지지 않음
  - `HGM2 -> HGMT`에서 `HGMT2`가 새로 만들어지지 않음
- 빌드된 실행 파일로 Pandora 제외 동작 확인:
  - `--skip-pandora`가 없으면 Pandora Output 프리셋이 적용됨
  - `--skip-pandora`가 있으면 Pandora arguments 프리셋이 적용되지 않음

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
CB7794C87C46B98BDE68C652EEB0B48CC80328EEBFEDDE486470A82B7D7A8F74  mo2-path-wizard-gui.zip
69EBA28A52F4400B91B55A1E9A1C2D31B4E041A74284F82218FBD69082EB3BC3  mo2-path-wizard-gui.exe
63EFEBE235CCA3890B83D7243420023850587889C3C80350120F0607EA57C85B  mo2-path-wizard.exe
```
