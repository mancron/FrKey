# hook_manager.py
import ctypes
import ctypes.wintypes
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

from accent_data  import ACCENT_MAP, TARGET_CHARS
from input_sender import OUR_EXTRA_INFO, send_backspace, send_unicode_char

user32 = ctypes.windll.user32

# ── LPARAM는 반드시 c_ssize_t (포인터 크기 = 64비트 on x64) ──────────
# ctypes.wintypes.LPARAM 은 내부적으로 c_long(32비트)이라 64비트 포인터가
# 오버플로우남. c_ssize_t 를 써야 정확하게 전달됨.
LPARAM_T = ctypes.c_ssize_t
WPARAM_T = ctypes.c_size_t

# ── 함수 시그니처 명시 ────────────────────────────────────────────────
user32.SetWindowsHookExW.restype   = ctypes.wintypes.HHOOK
user32.SetWindowsHookExW.argtypes  = [
    ctypes.c_int, ctypes.c_void_p, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD
]
user32.CallNextHookEx.restype      = ctypes.c_long
user32.CallNextHookEx.argtypes     = [
    ctypes.wintypes.HHOOK, ctypes.c_int, WPARAM_T, LPARAM_T
]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
user32.GetKeyState.restype         = ctypes.c_short

WH_KEYBOARD_LL = 13
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104
HC_ACTION      = 0

VK_HANJA  = 0x19
VK_BACK   = 0x08
VK_DELETE = 0x2E
VK_LEFT   = 0x25
VK_UP     = 0x26
VK_RIGHT  = 0x27
VK_DOWN   = 0x28
VK_HOME   = 0x24
VK_END    = 0x23
VK_PRIOR  = 0x21
VK_NEXT   = 0x22
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SHIFT  = 0x10
VK_CAPS   = 0x14

BUFFER_RESET_KEYS = frozenset({
    VK_DELETE, VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN,
    VK_HOME, VK_END, VK_PRIOR, VK_NEXT, VK_RETURN,
})

# HOOKPROC 시그니처도 LPARAM_T 사용
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    WPARAM_T,
    LPARAM_T,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('vkCode',      ctypes.wintypes.DWORD),
        ('scanCode',    ctypes.wintypes.DWORD),
        ('flags',       ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),  # ULONG_PTR
    ]


class HookManager(QObject):
    show_popup_signal = pyqtSignal(str, list)
    hide_popup_signal = pyqtSignal()

    def __init__(self, popup_window) -> None:
        super().__init__()
        self._buffer:          str       = ''
        self._popup_active:    bool      = False
        self._current_options: list[str] = []
        self._lock        = threading.Lock()
        self._hook_handle = None
        self._hook_proc   = None  # GC 방지

        self.show_popup_signal.connect(popup_window.show_popup)
        self.hide_popup_signal.connect(popup_window.hide_popup)
        popup_window.selection_made.connect(self._on_button_clicked)

    # ─────────────────────────────────────────────
    # 공개 메서드
    # ─────────────────────────────────────────────

    def start(self) -> None:
        self._hook_proc = HOOKPROC(self._hook_callback)

        self._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            None,   # WH_KEYBOARD_LL 은 hMod = NULL
            0,
        )
        if not self._hook_handle:
            err = ctypes.windll.kernel32.GetLastError()
            raise OSError(f"SetWindowsHookExW 실패: error={err}")

        print("[HookManager] 훅 설치 완료.")
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self) -> None:
        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None

    # ─────────────────────────────────────────────
    # 훅 콜백 — 절대 블로킹하면 안 됨 (Windows 타임아웃 있음)
    # ─────────────────────────────────────────────

    def _hook_callback(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code != HC_ACTION:
            return user32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

        kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode

        # 자체 SendInput 무시
        if kb.dwExtraInfo == OUR_EXTRA_INFO:
            return user32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

        if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            # 차단 여부만 결정; 무거운 작업은 절대 여기서 하지 않음
            if self._handle_keydown(vk):
                return 1

        return user32.CallNextHookEx(self._hook_handle, n_code, w_param, l_param)

    def _handle_keydown(self, vk: int) -> bool:
        """True 반환 시 해당 키 이벤트 차단."""
        with self._lock:
            popup_active    = self._popup_active
            current_options = self._current_options[:]

        # ── 팝업 활성 상태 ──────────────────────────────
        if popup_active:
            # 숫자 1~4 선택
            if 0x31 <= vk <= 0x39:
                idx = vk - 0x31
                if idx < len(current_options):
                    with self._lock:
                        self._popup_active = False
                    # ★ 반드시 별도 스레드로: 여기서 sleep/SendInput 하면
                    #   훅 스레드가 블로킹돼 Windows가 훅을 강제 해제함
                    threading.Thread(
                        target=self._apply_selection,
                        args=(idx,),
                        daemon=True,
                    ).start()
                    return True   # 숫자키 차단

            # ESC 취소
            elif vk == VK_ESCAPE:
                with self._lock:
                    self._popup_active = False
                    self._buffer       = ''
                self.hide_popup_signal.emit()
                return True

            # 그 외 키 → 팝업 닫고 키는 통과
            else:
                with self._lock:
                    self._popup_active = False
                self.hide_popup_signal.emit()
                # 아래 버퍼 관리로 fall-through

        # ── 한자 키 감지 ────────────────────────────────
        if vk == VK_HANJA:
            with self._lock:
                buf = self._buffer
            if buf in TARGET_CHARS:
                options = ACCENT_MAP[buf]
                with self._lock:
                    self._current_options = options
                    self._popup_active    = True
                self.show_popup_signal.emit(buf, options)
                return True   # 한자 키 차단
            return False      # Pass-through → OS 원래 기능 유지

        # ── 버퍼 관리 ───────────────────────────────────
        if vk == VK_BACK:
            with self._lock:
                self._buffer = ''
        elif vk in BUFFER_RESET_KEYS:
            with self._lock:
                self._buffer = ''
        else:
            char = self._vk_to_char(vk)
            with self._lock:
                self._buffer = char if char else ''

        return False

    # ─────────────────────────────────────────────
    # 선택 적용 (별도 스레드에서 실행)
    # ─────────────────────────────────────────────

    def _apply_selection(self, idx: int) -> None:
        """Backspace + 유니코드 전송. 훅 스레드 밖에서만 호출할 것."""
        with self._lock:
            chosen = self._current_options[idx]
            self._buffer = chosen

        self.hide_popup_signal.emit()
        time.sleep(0.020)    # Qt 큐 소화 대기 (팝업 숨김 완료)
        send_backspace()
        time.sleep(0.010)    # 대상 앱 처리 대기
        send_unicode_char(chosen)

    def _on_button_clicked(self, idx: int) -> None:
        """팝업 버튼 클릭 (메인 스레드)."""
        with self._lock:
            if not self._popup_active:
                return
            self._popup_active = False
        threading.Thread(
            target=self._apply_selection,
            args=(idx,),
            daemon=True,
        ).start()

    # ─────────────────────────────────────────────
    # VK → 문자 변환
    # ─────────────────────────────────────────────

    def _vk_to_char(self, vk: int) -> str | None:
        if 0x41 <= vk <= 0x5A:
            shift = bool(user32.GetKeyState(VK_SHIFT) & 0x8000)
            caps  = bool(user32.GetKeyState(VK_CAPS)  & 0x0001)
            upper = shift ^ caps
            return chr(vk) if upper else chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            if user32.GetKeyState(VK_SHIFT) & 0x8000:
                return None
            return chr(vk)
        return None