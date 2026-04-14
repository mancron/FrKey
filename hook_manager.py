# hook_manager.py
import ctypes
import ctypes.wintypes
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

from accent_data  import ACCENT_MAP, TARGET_CHARS, REVERSE_MAP
from input_sender import (
    OUR_EXTRA_INFO,
    send_backspace, send_ctrl_c, send_unicode_char,
    clipboard_get_text, clipboard_set_text,
)

user32 = ctypes.windll.user32

LPARAM_T = ctypes.c_ssize_t
WPARAM_T = ctypes.c_size_t

user32.SetWindowsHookExW.restype   = ctypes.wintypes.HHOOK
user32.SetWindowsHookExW.argtypes  = [
    ctypes.c_int, ctypes.c_void_p,
    ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD,
]
user32.CallNextHookEx.restype  = ctypes.c_long
user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK, ctypes.c_int, WPARAM_T, LPARAM_T,
]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
user32.GetGUIThreadInfo.restype    = ctypes.wintypes.BOOL
user32.ClientToScreen.restype      = ctypes.wintypes.BOOL
user32.GetKeyState.restype         = ctypes.c_short

WH_KEYBOARD_LL = 13
WH_CALLWNDPROC = 4
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104
WM_APPCOMMAND  = 0x0319
HC_ACTION      = 0

VK_BACK   = 0x08; VK_DELETE = 0x2E
VK_LEFT   = 0x25; VK_UP     = 0x26
VK_RIGHT  = 0x27; VK_DOWN   = 0x28
VK_HOME   = 0x24; VK_END    = 0x23
VK_PRIOR  = 0x21; VK_NEXT   = 0x22
VK_RETURN = 0x0D; VK_ESCAPE = 0x1B
VK_SHIFT  = 0x10; VK_CAPS   = 0x14

BUFFER_RESET_KEYS = frozenset({
    VK_DELETE, VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN,
    VK_HOME, VK_END, VK_PRIOR, VK_NEXT, VK_RETURN,
})

HOOKPROC_KB  = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, WPARAM_T, LPARAM_T)
HOOKPROC_WND = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, WPARAM_T, LPARAM_T)


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


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize',        ctypes.wintypes.DWORD),
        ('flags',         ctypes.wintypes.DWORD),
        ('hwndActive',    ctypes.wintypes.HWND),
        ('hwndFocus',     ctypes.wintypes.HWND),
        ('hwndCapture',   ctypes.wintypes.HWND),
        ('hwndMenuOwner', ctypes.wintypes.HWND),
        ('hwndMoveSize',  ctypes.wintypes.HWND),
        ('hwndCaret',     ctypes.wintypes.HWND),
        ('rcCaret',       ctypes.wintypes.RECT),
    ]


def get_caret_screen_pos() -> tuple[int, int] | None:
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
        return None
    if not info.hwndCaret:
        return None
    pt = ctypes.wintypes.POINT()
    pt.x = info.rcCaret.left
    pt.y = info.rcCaret.bottom
    if user32.ClientToScreen(info.hwndCaret, ctypes.byref(pt)):
        return pt.x, pt.y
    return None


class HookManager(QObject):
    show_popup_signal = pyqtSignal(str, list, int, int)
    hide_popup_signal = pyqtSignal()

    def __init__(self, popup_window, settings: dict) -> None:
        super().__init__()
        self._trigger_vk:         int | None = settings.get("trigger_vk")
        self._trigger_appcommand: int | None = settings.get("trigger_appcommand")
        self._buffer:          str        = ''
        self._popup_active:    bool       = False
        self._selection_mode:  bool       = False
        self._saved_clipboard: str | None = None
        self._current_options: list[str]  = []
        self._lock     = threading.Lock()
        self._hook_kb  = None
        self._hook_wnd = None
        self._proc_kb  = None
        self._proc_wnd = None

        self.show_popup_signal.connect(popup_window.show_popup)
        self.hide_popup_signal.connect(popup_window.hide_popup)
        popup_window.selection_made.connect(self._on_button_clicked)

    def update_settings(self, settings: dict) -> None:
        self._trigger_vk         = settings.get("trigger_vk")
        self._trigger_appcommand = settings.get("trigger_appcommand")

    def start(self) -> None:
        if self._trigger_vk is not None:
            self._proc_kb = HOOKPROC_KB(self._kb_callback)
            self._hook_kb = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._proc_kb, None, 0,
            )
            if not self._hook_kb:
                raise OSError(f"KB 훅 실패: {ctypes.windll.kernel32.GetLastError()}")
            print(f"[Hook] VK 훅  0x{self._trigger_vk:02X}")

        if self._trigger_appcommand is not None:
            self._proc_wnd = HOOKPROC_WND(self._wnd_callback)
            self._hook_wnd = user32.SetWindowsHookExW(
                WH_CALLWNDPROC, self._proc_wnd, None, 0,
            )
            if not self._hook_wnd:
                raise OSError(f"WND 훅 실패: {ctypes.windll.kernel32.GetLastError()}")
            print(f"[Hook] APPCOMMAND 훅  cmd={self._trigger_appcommand}")

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self) -> None:
        if self._hook_kb:
            user32.UnhookWindowsHookEx(self._hook_kb)
            self._hook_kb = None
        if self._hook_wnd:
            user32.UnhookWindowsHookEx(self._hook_wnd)
            self._hook_wnd = None

    def _kb_callback(self, n_code, w_param, l_param) -> int:
        if n_code != HC_ACTION:
            return user32.CallNextHookEx(self._hook_kb, n_code, w_param, l_param)
        kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        if kb.dwExtraInfo == OUR_EXTRA_INFO:
            return user32.CallNextHookEx(self._hook_kb, n_code, w_param, l_param)
        if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if self._handle_keydown(vk):
                return 1
        return user32.CallNextHookEx(self._hook_kb, n_code, w_param, l_param)

    def _wnd_callback(self, n_code, w_param, l_param) -> int:
        if n_code == HC_ACTION:
            cwp = ctypes.cast(l_param, ctypes.POINTER(CWPSTRUCT)).contents
            if cwp.message == WM_APPCOMMAND:
                cmd = (cwp.lParam >> 16) & 0xFFF
                if cmd == self._trigger_appcommand:
                    threading.Thread(target=self._on_trigger, daemon=True).start()
        return user32.CallNextHookEx(self._hook_wnd, n_code, w_param, l_param)

    def _handle_keydown(self, vk: int) -> bool:
        with self._lock:
            popup_active    = self._popup_active
            current_options = self._current_options[:]

        if popup_active:
            if 0x31 <= vk <= 0x39:
                idx = vk - 0x31
                if idx < len(current_options):
                    with self._lock:
                        self._popup_active = False
                    threading.Thread(
                        target=self._apply_selection, args=(idx,), daemon=True,
                    ).start()
                    return True
            elif vk == VK_ESCAPE:
                with self._lock:
                    self._popup_active   = False
                    self._selection_mode = False
                    self._buffer         = ''
                self._restore_clipboard()
                self.hide_popup_signal.emit()
                return True
            else:
                with self._lock:
                    self._popup_active   = False
                    self._selection_mode = False
                self._restore_clipboard()
                self.hide_popup_signal.emit()

        if vk == self._trigger_vk:
            threading.Thread(target=self._on_trigger, daemon=True).start()
            return True

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

    def _on_trigger(self) -> None:
        with self._lock:
            buf = self._buffer
        if buf in TARGET_CHARS:
            options = ACCENT_MAP[buf]
            pos     = get_caret_screen_pos()
            x, y    = (pos[0], pos[1]) if pos else (-1, -1)
            with self._lock:
                self._current_options = options
                self._popup_active    = True
                self._selection_mode  = False
            self.show_popup_signal.emit(buf, options, x, y)
        else:
            self._try_selection_mode()

    def _try_selection_mode(self) -> None:
        saved = clipboard_get_text()
        send_ctrl_c()
        time.sleep(0.08)
        selected = clipboard_get_text()
        if selected and len(selected) == 1 and selected in REVERSE_MAP:
            base, options = REVERSE_MAP[selected]
            pos  = get_caret_screen_pos()
            x, y = (pos[0], pos[1]) if pos else (-1, -1)
            with self._lock:
                self._current_options = options
                self._popup_active    = True
                self._selection_mode  = True
                self._saved_clipboard = saved
            self.show_popup_signal.emit(base, options, x, y)
        else:
            if saved is not None:
                clipboard_set_text(saved)

    def _restore_clipboard(self) -> None:
        with self._lock:
            saved = self._saved_clipboard
            self._saved_clipboard = None
        if saved is not None:
            clipboard_set_text(saved)

    def _apply_selection(self, idx: int) -> None:
        with self._lock:
            chosen         = self._current_options[idx]
            selection_mode = self._selection_mode
            self._buffer   = chosen
        self.hide_popup_signal.emit()
        time.sleep(0.020)
        if selection_mode:
            send_unicode_char(chosen)
            time.sleep(0.030)
            self._restore_clipboard()
        else:
            send_backspace()
            time.sleep(0.010)
            send_unicode_char(chosen)

    def _on_button_clicked(self, idx: int) -> None:
        with self._lock:
            if not self._popup_active:
                return
            self._popup_active = False
        threading.Thread(
            target=self._apply_selection, args=(idx,), daemon=True,
        ).start()

    def _vk_to_char(self, vk: int) -> str | None:
        if 0x41 <= vk <= 0x5A:
            shift = bool(user32.GetKeyState(VK_SHIFT) & 0x8000)
            caps  = bool(user32.GetKeyState(VK_CAPS)  & 0x0001)
            upper = shift ^ caps
            return chr(vk) if upper else chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return None if (user32.GetKeyState(VK_SHIFT) & 0x8000) else chr(vk)
        return None