# Accent Input Helper

한자 키를 이용해 프랑스어/스페인어 성조 문자를 빠르게 입력하는 윈도우 백그라운드 유틸리티.

## 작동 방식

1. 알파벳을 타이핑 (`a`, `e`, `i`, `o`, `u` 등)
2. 바로 **[한자]** 키 누름
3. 팝업에서 숫자키 1~4 로 선택 → 자동 치환

예: `e` → `[한자]` → `1` 입력 시 `e`가 `é`로 교체됨

## 지원 문자

| 입력 | 선택지 |
|------|--------|
| a / A | á à â ä / Á À Â Ä |
| e / E | é è ê ë / É È Ê Ë |
| i / I | í ì î ï / Í Ì Î Ï |
| o / O | ó ò ô ö / Ó Ò Ô Ö |
| u / U | ú ù û ü / Ú Ù Û Ü |
| n / N | ñ ń / Ñ Ń |
| c / C | ç ć / Ç Ć |
| s / S | ś š / Ś Š |
| z / Z | ź ż ž / Ź Ż Ž |
| y / Y | ý ÿ / Ý Ÿ |

## 설치

```bash
pip install -r requirements.txt
python main.py
```

## 기술 스택

- **Python 3.11+** (Windows 전용)
- **PyQt6** — 팝업 UI (WS_EX_NOACTIVATE 플래그로 포커스 비탈취)
- **ctypes** — WH_KEYBOARD_LL 저수준 훅 + SendInput (KEYEVENTF_UNICODE)
- **pywin32** — 보조 Windows API 접근

## 주의사항

- Windows 전용 (한자 키 VK_HANJA = 0x19)
- 일부 보안 소프트웨어/게임 안티치트에서 키보드 훅을 차단할 수 있음
- 관리자 권한 불필요 (WH_KEYBOARD_LL은 일반 권한으로 동작)

## 파일 구조

```
accent_input/
├── main.py           진입점, 시스템 트레이
├── hook_manager.py   WH_KEYBOARD_LL 훅 + 상태 머신
├── popup_window.py   PyQt6 오버레이 팝업 (WS_EX_NOACTIVATE)
├── input_sender.py   SendInput 래퍼 (유니코드 전송)
├── accent_data.py    성조 문자 매핑 딕셔너리
└── requirements.txt
```
