# input_sender.py
import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

INPUT_KEYBOARD    = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP   = 0x0002
VK_BACK           = 0x08

OUR_EXTRA_INFO = 0xDEADBEEF


# ── 구조체 정의 (64비트 올바른 크기) ──────────────────────────────────
# dwExtraInfo = ULONG_PTR → 반드시 c_size_t (8바이트 on x64)
# c_ulong 을 쓰면 4바이트라 구조체 전체 레이아웃이 틀어져 SendInput 무동작

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk',         ctypes.wintypes.WORD),
        ('wScan',       ctypes.wintypes.WORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),   # ULONG_PTR (8 bytes on x64)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.wintypes.LONG),
        ('dy',          ctypes.wintypes.LONG),
        ('mouseData',   ctypes.wintypes.DWORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),   # ULONG_PTR
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg',    ctypes.wintypes.DWORD),
        ('wParamL', ctypes.wintypes.WORD),
        ('wParamH', ctypes.wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    # 세 멤버 모두 선언해야 Union 크기 = max(28,20,8) = 28 바이트
    # 하나만 선언하면 크기가 작아져 INPUT 전체가 틀어짐
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ('_u',)
    _fields_ = [
        ('type', ctypes.wintypes.DWORD),
        ('_u',   _INPUT_UNION),
    ]
    # x64 기준 sizeof(INPUT) == 40 bytes
    # type(4) + padding(4) + union(28) + end-padding(4) = 40

# ── SendInput 시그니처 명시 ────────────────────────────────────────────
user32.SendInput.restype  = ctypes.wintypes.UINT
user32.SendInput.argtypes = [
    ctypes.wintypes.UINT,   # cInputs
    ctypes.POINTER(INPUT),  # pInputs
    ctypes.c_int,           # cbSize
]


def _make_key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type            = INPUT_KEYBOARD
    inp.ki.wVk          = vk
    inp.ki.wScan        = scan
    inp.ki.dwFlags      = flags
    inp.ki.time         = 0
    inp.ki.dwExtraInfo  = OUR_EXTRA_INFO
    return inp


def send_backspace() -> None:
    arr = (INPUT * 2)(
        _make_key(vk=VK_BACK, flags=0),
        _make_key(vk=VK_BACK, flags=KEYEVENTF_KEYUP),
    )
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def send_unicode_char(char: str) -> None:
    cp = ord(char)
    if cp > 0xFFFF:
        # 서로게이트 쌍
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