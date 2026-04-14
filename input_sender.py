# input_sender.py
import ctypes
import ctypes.wintypes
import time

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD    = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP   = 0x0002
VK_BACK           = 0x08
VK_CONTROL        = 0x11
VK_C              = 0x43

OUR_EXTRA_INFO = 0xDEADBEEF

CF_UNICODETEXT = 13
GMEM_MOVEABLE  = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk',         ctypes.wintypes.WORD),
        ('wScan',       ctypes.wintypes.WORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.wintypes.LONG),
        ('dy',          ctypes.wintypes.LONG),
        ('mouseData',   ctypes.wintypes.DWORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg',    ctypes.wintypes.DWORD),
        ('wParamL', ctypes.wintypes.WORD),
        ('wParamH', ctypes.wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ('_u',)
    _fields_    = [('type', ctypes.wintypes.DWORD), ('_u', _INPUT_UNION)]

user32.SendInput.restype  = ctypes.wintypes.UINT
user32.SendInput.argtypes = [
    ctypes.wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int
]


def _make_key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type           = INPUT_KEYBOARD
    inp.ki.wVk         = vk
    inp.ki.wScan       = scan
    inp.ki.dwFlags     = flags
    inp.ki.time        = 0
    inp.ki.dwExtraInfo = OUR_EXTRA_INFO
    return inp


def send_backspace() -> None:
    arr = (INPUT * 2)(
        _make_key(vk=VK_BACK, flags=0),
        _make_key(vk=VK_BACK, flags=KEYEVENTF_KEYUP),
    )
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def send_ctrl_c() -> None:
    """선택 영역 복사 (드래그 재변환용)."""
    arr = (INPUT * 4)(
        _make_key(vk=VK_CONTROL, flags=0),
        _make_key(vk=VK_C,       flags=0),
        _make_key(vk=VK_C,       flags=KEYEVENTF_KEYUP),
        _make_key(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP),
    )
    user32.SendInput(4, arr, ctypes.sizeof(INPUT))


def send_unicode_char(char: str) -> None:
    cp = ord(char)
    if cp > 0xFFFF:
        cp -= 0x10000
        _send_scan(0xD800 + (cp >> 10))
        _send_scan(0xDC00 + (cp & 0x3FF))
    else:
        _send_scan(cp)


def _send_scan(scan: int) -> None:
    arr = (INPUT * 2)(
        _make_key(scan=scan, flags=KEYEVENTF_UNICODE),
        _make_key(scan=scan, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
    )
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


# ── 클립보드 (드래그 재변환 전용) ─────────────────────────────────────

def clipboard_get_text() -> str | None:
    """현재 클립보드 텍스트 반환. 실패 시 None."""
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        text = ctypes.wstring_at(ptr)
        kernel32.GlobalUnlock(handle)
        return text
    except Exception:
        return None
    finally:
        user32.CloseClipboard()


def clipboard_set_text(text: str) -> bool:
    """클립보드에 텍스트 저장. 성공 시 True."""
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        encoded = (text + '\0').encode('utf-16-le')
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
        return True
    except Exception:
        return False
    finally:
        user32.CloseClipboard()