# popup_window.py
import ctypes
import ctypes.wintypes
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore    import Qt, pyqtSignal
from PyQt6.QtGui     import QCursor

GWL_EXSTYLE      = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PopupWindow(QWidget):
    selection_made = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
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
        # 레이아웃은 self에 딱 하나만
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)

        self.setObjectName("popup_root")
        self.setStyleSheet("""
            QWidget#popup_root {
                background-color: rgba(24, 24, 28, 230);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.07);
                color: #F0F0F0;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 17px;
                font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
                min-width: 36px;
            }
            QPushButton:hover {
                background-color: rgba(100, 140, 255, 0.45);
                border-color: rgba(120, 160, 255, 0.7);
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: rgba(80, 120, 220, 0.6);
            }
            QLabel {
                color: rgba(255, 255, 255, 0.35);
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
                border: none;
                padding-left: 4px;
            }
        """)

        self._buttons: list[QPushButton] = []
        for i in range(9):
            btn = QPushButton()
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _, idx=i: self.selection_made.emit(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        self._hint = QLabel("ESC")
        layout.addWidget(self._hint)

    def _apply_no_activate(self) -> None:
        self.show()
        self.hide()
        hwnd    = int(self.winId())
        current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            current | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )

    def show_popup(self, char: str, options: list[str]) -> None:
        for i, btn in enumerate(self._buttons):
            if i < len(options):
                btn.setText(f"{i + 1}.{options[i]}")
                btn.setVisible(True)
            else:
                btn.setVisible(False)

        self.adjustSize()

        pos    = QCursor.pos()
        screen = self.screen().availableGeometry()
        x = pos.x() + 12
        y = pos.y() - self.height() - 14

        if x + self.width() > screen.right():
            x = pos.x() - self.width() - 12
        if y < screen.top():
            y = pos.y() + 20
        if x < screen.left():
            x = screen.left() + 8

        self.move(x, y)
        self.show()
        self.raise_()

    def hide_popup(self) -> None:
        self.hide()