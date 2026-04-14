# popup_window.py
import ctypes
import ctypes.wintypes
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtGui     import QCursor

from style_dialog import DEFAULT_STYLE, _hex_with_opacity

GWL_EXSTYLE      = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PopupWindow(QWidget):
    selection_made = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self._style = dict(DEFAULT_STYLE)
        self._setup_window_flags()
        self._setup_ui()
        self._apply_no_activate()

    def _setup_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Tool                 |
            Qt.WindowType.FramelessWindowHint  |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _setup_ui(self) -> None:
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 7, 10, 7)
        self._layout.setSpacing(4)
        self.setObjectName("popup_root")

        self._buttons: list[QPushButton] = []
        for i in range(9):
            btn = QPushButton()
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _, idx=i: self.selection_made.emit(idx))
            self._layout.addWidget(btn)
            self._buttons.append(btn)

        self._hint = QLabel("ESC")
        self._layout.addWidget(self._hint)

        self._apply_style()

    def _apply_style(self) -> None:
        s       = self._style
        opacity = s.get("opacity", 235)
        bg      = _hex_with_opacity(s.get("bg_color",     "#18181c"), opacity)
        btn_bg  = s.get("btn_color",    "#ffffff12")
        text    = s.get("text_color",   "#f0f0f0")
        border  = s.get("border_color", "#ffffff1e")

        self.setStyleSheet(f"""
            QWidget#popup_root {{
                background-color: {bg};
                border-radius: 10px;
                border: 1px solid {border};
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 16px;
                font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
                min-width: 34px;
            }}
            QPushButton:hover {{
                background-color: rgba(100,140,255,0.45);
                border-color: rgba(120,160,255,0.7);
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: rgba(80,120,220,0.6);
            }}
            QLabel {{
                color: {text};
                font-size: 10px;
                background: transparent;
                border: none;
                padding-left: 2px;
            }}
        """)

    def apply_popup_style(self, style: dict) -> None:
        """외부에서 실시간으로 스타일 업데이트 (미리보기용)."""
        self._style = style
        self._apply_style()

    def _apply_no_activate(self) -> None:
        self.show()
        self.hide()
        hwnd    = int(self.winId())
        current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            current | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )

    def show_popup(self, char: str, options: list[str], caret_x: int, caret_y: int) -> None:
        for i, btn in enumerate(self._buttons):
            if i < len(options):
                btn.setText(f"{i+1}.{options[i]}")
                btn.setVisible(True)
            else:
                btn.setVisible(False)

        self.adjustSize()
        screen = self.screen().availableGeometry()

        if caret_x >= 0 and caret_y >= 0:
            # 네이티브 앱: 캐럿(텍스트 커서) 바로 아래
            x, y = caret_x, caret_y + 4
        else:
            # Electron 등 폴백: 마우스 커서 바로 위
            # (타이핑 중 마우스는 텍스트 근처에 있으므로 위쪽이 자연스러움)
            pos  = QCursor.pos()
            x    = pos.x() - self.width() // 2   # 마우스 중앙 기준 수평 정렬
            y    = pos.y() - self.height() - 12  # 마우스 위쪽

        if x + self.width()  > screen.right():  x = screen.right()  - self.width()  - 4
        if y + self.height() > screen.bottom(): y = (caret_y - self.height() - 4) if caret_y >= 0 else y - self.height() - 20
        if x < screen.left():  x = screen.left()  + 4
        if y < screen.top():   y = screen.top()   + 4

        self.move(x, y)
        self.show()
        self.raise_()

    def hide_popup(self) -> None:
        self.hide()