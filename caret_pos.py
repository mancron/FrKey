# caret_pos.py
# 텍스트 커서 위치를 화면 좌표로 얻어오는 모듈
# 세 가지 방법을 순서대로 시도하고 안 되면 None 반환

import ctypes
import ctypes.wintypes

user32   = ctypes.windll.user32
oleacc   = ctypes.windll.oleacc

LPARAM_T = ctypes.c_ssize_t
WPARAM_T = ctypes.c_size_t

# ── 시그니처 ──────────────────────────────────────────────────────────
user32.GetForegroundWindow.restype          = ctypes.wintypes.HWND
user32.GetWindowThreadProcessId.restype     = ctypes.wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes    = [
    ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)
]
user32.GetGUIThreadInfo.restype  = ctypes.wintypes.BOOL
user32.ClientToScreen.restype    = ctypes.wintypes.BOOL


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


# IAccessible OBJID_CARET — Win32 캐럿 없는 앱용 (IE, 레거시 앱 일부)
OBJID_CARET = ctypes.c_long(0xFFFFFFF8)

class VARIANT(ctypes.Structure):
    class _U(ctypes.Union):
        class _S(ctypes.Structure):
            _fields_ = [("vt", ctypes.c_ushort), ("wReserved1", ctypes.c_ushort),
                        ("wReserved2", ctypes.c_ushort), ("wReserved3", ctypes.c_ushort)]
        _fields_ = [("s", _S), ("d", ctypes.c_double)]
    _anonymous_ = ("_u",)
    _fields_    = [("_u", _U)]


def _method1_gui_thread(hwnd_fg: int) -> tuple[int, int] | None:
    """GetGUIThreadInfo — 포그라운드 창의 스레드 ID를 명시해서 캐럿 위치 획득.
    메모장, Word, 한글, 네이티브 앱에서 동작.
    """
    thread_id = user32.GetWindowThreadProcessId(hwnd_fg, None)
    if not thread_id:
        return None

    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return None
    if not info.hwndCaret:
        return None

    pt = ctypes.wintypes.POINT()
    pt.x = info.rcCaret.left
    pt.y = info.rcCaret.bottom  # 글자 아랫줄 → 팝업이 바로 밑에
    if user32.ClientToScreen(info.hwndCaret, ctypes.byref(pt)):
        return pt.x, pt.y
    return None


def _method2_accessible(hwnd_fg: int) -> tuple[int, int] | None:
    """AccessibleObjectFromWindow(OBJID_CARET) — IAccessible 캐럿.
    일부 레거시 앱 / 네이티브 컨트롤에서 method1이 실패할 때 보조.
    """
    try:
        import comtypes
        import comtypes.client
        IID_IAccessible = comtypes.GUID("{618736E0-3C3D-11CF-810C-00AA00389B71}")
        acc   = ctypes.c_void_p()
        child = VARIANT()
        hr = oleacc.AccessibleObjectFromWindow(
            hwnd_fg, OBJID_CARET,
            ctypes.byref(IID_IAccessible),
            ctypes.byref(acc),
        )
        if hr != 0 or not acc:
            return None
        x = ctypes.c_long(); y = ctypes.c_long()
        w = ctypes.c_long(); h = ctypes.c_long()
        # IAccessible::accLocation (vtable offset 22)
        # comtypes 없이 vtable 직접 접근은 복잡하므로 여기선 None 반환
        return None
    except Exception:
        return None


def get_caret_screen_pos() -> tuple[int, int] | None:
    """텍스트 커서(캐럿)의 화면 절대 좌표 반환.

    우선순위:
      1. GetGUIThreadInfo (네이티브 앱)
      2. 실패 시 None → 호출부에서 마우스 위치로 폴백

    Chrome/VSCode/Discord 등 Electron 앱은 Win32 캐럿 API를
    사용하지 않아 어떤 방법으로도 OS에서 좌표를 얻을 수 없음.
    이 경우 None을 반환하면 호출부에서 마우스 기준으로 표시.
    """
    hwnd_fg = user32.GetForegroundWindow()
    if not hwnd_fg:
        return None

    pos = _method1_gui_thread(hwnd_fg)
    if pos:
        return pos

    return None