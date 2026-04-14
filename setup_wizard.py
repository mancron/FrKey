# setup_wizard.py
# 트리거 키 설정 마법사 UI
# 첫 실행 또는 트레이 "설정"에서 호출됨

import ctypes
import ctypes.wintypes
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore    import Qt, pyqtSignal, QTimer
from PyQt6.QtGui     import QFont, QColor

import settings_storage

LPARAM_T = ctypes.c_ssize_t
WPARAM_T = ctypes.c_size_t

user32 = ctypes.windll.user32

WH_KEYBOARD_LL = 13
WH_CALLWNDPROC = 4
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104
WM_APPCOMMAND  = 0x0319
HC_ACTION      = 0

HOOKPROC_KB  = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, WPARAM_T, LPARAM_T)
HOOKPROC_WND = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, WPARAM_T, LPARAM_T)

# 무시할 단독 수식키 (Shift, Ctrl, Alt, Win 등)
MODIFIER_VKS = frozenset({
    0x10, 0x11, 0x12,        # Shift, Ctrl, Alt
    0xA0, 0xA1,              # LShift, RShift
    0xA2, 0xA3,              # LCtrl, RCtrl
    0xA4, 0xA5,              # LAlt, RAlt
    0x5B, 0x5C,              # LWin, RWin
    0x14, 0x90, 0x91,        # CapsLock, NumLock, ScrollLock (수식키로 취급 안 함)
})

# APPCOMMAND 번호 → 이름
APPCOMMAND_NAMES = {
    18: "계산기",
    17: "앱1",
    15: "메일",
    16: "미디어",
    8:  "재생/일시정지",
    9:  "미디어 정지",
    11: "다음 트랙",
    12: "이전 트랙",
    13: "음소거",
}

# VK → 사람이 읽을 수 있는 이름
VK_NAMES = {
    0x19: "한자",
    0xB7: "계산기",
    0x91: "ScrollLock",
    0x13: "Pause/Break",
    0x2D: "Insert",
    0x7B: "F12", 0x7C: "F13", 0x7D: "F14",
}

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode',      ctypes.wintypes.DWORD),
        ('scanCode',    ctypes.wintypes.DWORD),
        ('flags',       ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

class CWPSTRUCT(ctypes.Structure):
    _fields_ = [
        ('lParam',  LPARAM_T),
        ('wParam',  WPARAM_T),
        ('message', ctypes.wintypes.UINT),
        ('hwnd',    ctypes.wintypes.HWND),
    ]

user32.SetWindowsHookExW.restype  = ctypes.wintypes.HHOOK
user32.CallNextHookEx.restype     = ctypes.c_long
user32.CallNextHookEx.argtypes    = [
    ctypes.wintypes.HHOOK, ctypes.c_int, WPARAM_T, LPARAM_T,
]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL


class SetupWizard(QDialog):
    """트리거 키 설정 다이얼로그.
    완료 시 settings_storage에 저장하고 accepted 시그널 방출.
    """
    key_detected = pyqtSignal(dict)   # 내부 스레드 → UI 스레드 전달용

    def __init__(self, parent=None, is_reconfig: bool = False) -> None:
        super().__init__(parent)
        self._is_reconfig  = is_reconfig
        self._hook_kb      = None
        self._hook_wnd     = None
        self._proc_kb      = None
        self._proc_wnd     = None
        self._pending      = None   # 감지된 설정 (확인 대기 중)
        self._listening    = False

        self.key_detected.connect(self._on_key_detected)
        self._setup_ui()
        self._start_hooks()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setWindowTitle("Accent Input — 트리거 키 설정")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e22;
            }
            QLabel {
                color: #e0e0e0;
                background: transparent;
            }
            QPushButton {
                background-color: #3a3a44;
                color: #e0e0e0;
                border: 1px solid #55556a;
                border-radius: 7px;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4e4e66;
                border-color: #8888bb;
            }
            QPushButton#confirm_btn {
                background-color: #4060cc;
                border-color: #6080ee;
                color: #ffffff;
            }
            QPushButton#confirm_btn:hover {
                background-color: #5070dd;
            }
            QPushButton#confirm_btn:disabled {
                background-color: #2a2a3a;
                border-color: #3a3a4a;
                color: #666;
            }
            QFrame#key_box {
                background-color: #13131a;
                border: 2px dashed #3a3a55;
                border-radius: 12px;
            }
            QFrame#key_box[state="listening"] {
                border-color: #5577ff;
            }
            QFrame#key_box[state="detected"] {
                border: 2px solid #44bb77;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 24)
        root.setSpacing(18)

        # 제목
        title = QLabel("트리거 키 설정" if not self._is_reconfig else "트리거 키 재설정")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
        title.setStyleSheet("color: #ffffff;")
        root.addWidget(title)

        # 설명
        desc = QLabel(
            "성조 문자 팝업을 열 키를 지정합니다.\n"
            "아래 영역을 클릭한 뒤 원하는 키를 누르세요.\n"
            "한자 키, 계산기 키, F13 등 거의 모든 키가 가능합니다."
        )
        desc.setStyleSheet("color: #aaa; font-size: 13px; line-height: 1.6;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # 키 감지 박스
        self._key_box = QFrame()
        self._key_box.setObjectName("key_box")
        self._key_box.setProperty("state", "listening")
        self._key_box.setFixedHeight(100)
        self._key_box.setCursor(Qt.CursorShape.PointingHandCursor)
        self._key_box.mousePressEvent = lambda _: self._activate_listening()

        box_layout = QVBoxLayout(self._key_box)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._key_icon = QLabel("⌨")
        self._key_icon.setFont(QFont("Segoe UI", 26))
        self._key_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_icon.setStyleSheet("color: #5577ff; background: transparent;")
        box_layout.addWidget(self._key_icon)

        self._key_label = QLabel("클릭 후 키를 누르세요")
        self._key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._key_label.setStyleSheet("color: #666; font-size: 13px; background: transparent;")
        box_layout.addWidget(self._key_label)

        root.addWidget(self._key_box)

        # 감지된 키 정보 표시
        self._info_label = QLabel("")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: #44bb77; font-size: 12px;")
        self._info_label.setVisible(False)
        root.addWidget(self._info_label)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._retry_btn = QPushButton("다시 설정")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(self._reset_detection)
        btn_row.addWidget(self._retry_btn)

        btn_row.addStretch()

        self._confirm_btn = QPushButton("이 키로 사용")
        self._confirm_btn.setObjectName("confirm_btn")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self._confirm_btn)

        root.addLayout(btn_row)

        # 첫 실행이면 바로 리스닝 활성화
        QTimer.singleShot(300, self._activate_listening)

    # ─────────────────────────────────────────────
    # 리스닝 상태 관리
    # ─────────────────────────────────────────────

    def _activate_listening(self) -> None:
        self._listening = True
        self._pending   = None
        self._key_box.setProperty("state", "listening")
        self._key_box.style().unpolish(self._key_box)
        self._key_box.style().polish(self._key_box)
        self._key_icon.setStyleSheet("color: #5577ff; background: transparent;")
        self._key_label.setText("키를 누르세요...")
        self._key_label.setStyleSheet("color: #5577ff; font-size: 13px; background: transparent;")
        self._info_label.setVisible(False)
        self._confirm_btn.setEnabled(False)
        self._retry_btn.setVisible(False)

    def _reset_detection(self) -> None:
        self._activate_listening()

    # ─────────────────────────────────────────────
    # 키 감지 (훅 콜백 → 시그널 → UI)
    # ─────────────────────────────────────────────

    def _on_key_detected(self, info: dict) -> None:
        """Qt 메인 스레드에서 UI 업데이트."""
        if not self._listening:
            return
        self._listening = False
        self._pending   = info

        label = info["label"]
        mode  = "VK" if info.get("trigger_vk") else "APPCOMMAND"

        self._key_box.setProperty("state", "detected")
        self._key_box.style().unpolish(self._key_box)
        self._key_box.style().polish(self._key_box)
        self._key_icon.setText("✓")
        self._key_icon.setStyleSheet("color: #44bb77; background: transparent;")
        self._key_label.setText(label)
        self._key_label.setStyleSheet(
            "color: #ffffff; font-size: 15px; font-weight: 500; background: transparent;"
        )
        self._info_label.setText(f"감지 방식: {mode}")
        self._info_label.setVisible(True)
        self._confirm_btn.setEnabled(True)
        self._retry_btn.setVisible(True)

    # ─────────────────────────────────────────────
    # 확인 → 저장
    # ─────────────────────────────────────────────

    def _confirm(self) -> None:
        if not self._pending:
            return
        settings_storage.save(self._pending)
        self._stop_hooks()
        self.accept()

    # ─────────────────────────────────────────────
    # 훅 (키 감지용, 마법사가 떠 있는 동안만)
    # ─────────────────────────────────────────────

    def _start_hooks(self) -> None:
        self._proc_kb = HOOKPROC_KB(self._kb_cb)
        self._proc_wnd = HOOKPROC_WND(self._wnd_cb)
        self._hook_kb  = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc_kb,  None, 0)
        self._hook_wnd = user32.SetWindowsHookExW(WH_CALLWNDPROC,  self._proc_wnd, None, 0)

    def _stop_hooks(self) -> None:
        if self._hook_kb:
            user32.UnhookWindowsHookEx(self._hook_kb)
            self._hook_kb = None
        if self._hook_wnd:
            user32.UnhookWindowsHookEx(self._hook_wnd)
            self._hook_wnd = None

    def _kb_cb(self, n_code, w_param, l_param) -> int:
        if n_code == HC_ACTION and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            if self._listening and vk not in MODIFIER_VKS:
                name = VK_NAMES.get(vk) or f"키 0x{vk:02X}"
                self.key_detected.emit({
                    "trigger_vk":         vk,
                    "trigger_appcommand": None,
                    "trigger_label":      name,
                    "label":              name,
                })
        return user32.CallNextHookEx(self._hook_kb, n_code, w_param, l_param)

    def _wnd_cb(self, n_code, w_param, l_param) -> int:
        if n_code == HC_ACTION:
            cwp = ctypes.cast(l_param, ctypes.POINTER(CWPSTRUCT)).contents
            if cwp.message == WM_APPCOMMAND and self._listening:
                cmd  = (cwp.lParam >> 16) & 0xFFF
                name = APPCOMMAND_NAMES.get(cmd, f"특수키 #{cmd}")
                self.key_detected.emit({
                    "trigger_vk":         None,
                    "trigger_appcommand": cmd,
                    "trigger_label":      name,
                    "label":              name,
                })
        return user32.CallNextHookEx(self._hook_wnd, n_code, w_param, l_param)

    def closeEvent(self, event) -> None:
        self._stop_hooks()
        super().closeEvent(event)