# v1.0.3 - GUI 시각 개선

## 개요

이번 릴리즈는 `v1.0.2`의 Pandora 제외, 안전한 경로 치환, 자동감지 수정은 그대로 유지하면서 GUI를 더 보기 좋고 읽기 편하게 다듬은 버전입니다.

## 변경된 점

- 상단 헤더 영역을 추가해 도구 이름과 목적이 더 잘 보이도록 정리했습니다.
- 모드팩, 실행 옵션, 고급 경로, 미리보기/실행 결과 영역을 더 명확하게 구분했습니다.
- 미리보기와 적용 버튼을 더 크고 선명하게 배치했습니다.
- 결과 출력창을 어두운 콘솔 스타일로 변경했습니다.
- diff 결과 색상을 어두운 출력창에서 더 잘 보이도록 조정했습니다.
- `Output`, `Ready`, `Detecting...`, `Preview complete` 등 영어 상태 문구를 한국어로 교체했습니다.
- `Options`, `Advanced Paths` 같은 섹션명을 한국어로 교체했습니다.
- 경로 입력 행, 찾아보기 버튼, 체크박스 간격을 정리했습니다.

## 유지되는 주요 수정

- Pandora 자동 추가와 arguments 프리셋 적용을 제외하는 옵션을 유지합니다.
- `HGM -> HGM2 -> HGM22`처럼 폴더명 뒤에 문자가 누적되던 경로 치환 문제 수정이 유지됩니다.
- `G:\TAKEALOOK` 구조에서 `TOOLS` 폴더를 찾지 못하던 자동감지 문제 수정이 유지됩니다.

## 검증 내용

- GUI 인스턴스 생성 후 즉시 종료하는 방식으로 Tkinter 런타임 오류가 없는지 확인했습니다.
- 전체 테스트 실행:
  - 명령: `python -m unittest discover -s tests -p "test*.py" -v`
  - 결과: 테스트 `14`개 통과
- PyInstaller `6.14.2`로 CLI/GUI 실행 파일을 다시 빌드했습니다.
- `mo2-path-wizard-gui.exe`를 새로 압축해 `mo2-path-wizard-gui.zip`을 갱신했습니다.

## 권장 다운로드

- `mo2-path-wizard-gui.zip`

## 추가 다운로드

- `mo2-path-wizard-gui.exe`
- `mo2-path-wizard.exe`

## SHA256

```text
F63067163F6C433F5289D80007D74656E7B6BD4971E0B9D7D96E36CCD6051F8A  mo2-path-wizard-gui.zip
A77BF6D389BC554873F1D3A68DF986F69C57099542316DC5BE34BB1E0B0DCB74  mo2-path-wizard-gui.exe
BA5CD3407F498C0DFDCB8E364CD18619F86B341F167B37AEB0A86FB5D959A931  mo2-path-wizard.exe
```
