# style_dialog.py
# 팝업 스타일 설정 다이얼로그 (배경색, 투명도, 버튼색, 글자색)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QFrame, QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui  import QFont, QColor

import settings_storage

DEFAULT_STYLE = {
    "bg_color":     "#18181c",
    "btn_color":    "#ffffff12",
    "text_color":   "#f0f0f0",
    "border_color": "#ffffff1e",
    "opacity":      235,          # 0~255
}


def _hex_with_opacity(hex6: str, opacity: int) -> str:
    """#rrggbb + opacity(0~255) → rgba(r,g,b,a) 문자열."""
    h = hex6.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{opacity})"


class ColorButton(QPushButton):
    """색상 미리보기 + 클릭 시 컬러피커를 여는 버튼."""
    color_changed = pyqtSignal(str)

    def __init__(self, color: str, label: str = "") -> None:
        super().__init__(label)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 6px;
                min-width: 48px;
                min-height: 28px;
            }}
            QPushButton:hover {{ border-color: rgba(255,255,255,0.6); }}
        """)

    def _pick(self) -> None:
        c = QColorDialog.getColor(
            QColor(self._color), self,
            options=QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.color_changed.emit(self._color)

    def color(self) -> str:
        return self._color

    def set_color(self, c: str) -> None:
        self._color = c
        self._refresh()


class StyleDialog(QDialog):
    style_changed = pyqtSignal(dict)   # 실시간 미리보기용

    def __init__(self, current_style: dict, parent=None) -> None:
        super().__init__(parent)
        self._style = {**DEFAULT_STYLE, **current_style}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("팝업 스타일 설정")
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QDialog { background: #1e1e26; }
            QLabel  { color: #cccccc; font-size: 13px; background: transparent; }
            QLabel#section { color: #ffffff; font-size: 14px; font-weight: 500; }
            QPushButton#action {
                background: #3a3a50; color: #e0e0e0;
                border: 1px solid #55556a; border-radius: 7px;
                padding: 7px 18px; font-size: 13px;
            }
            QPushButton#action:hover { background: #4e4e6a; }
            QPushButton#save {
                background: #4060cc; color: #fff;
                border: 1px solid #6080ee; border-radius: 7px;
                padding: 7px 20px; font-size: 13px;
            }
            QPushButton#save:hover { background: #5070dd; }
            QSlider::groove:horizontal {
                height: 4px; background: #3a3a50; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 16px; height: 16px; margin: -6px 0;
                background: #6080ee; border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #6080ee; border-radius: 2px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(16)

        # 제목
        t = QLabel("팝업 스타일")
        t.setObjectName("section")
        t.setFont(QFont("Segoe UI", 15, QFont.Weight.Medium))
        root.addWidget(t)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333344;")
        root.addWidget(line)

        # 색상 그리드
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)

        labels = ["배경색", "버튼색", "글자색", "테두리색"]
        keys   = ["bg_color", "btn_color", "text_color", "border_color"]
        self._color_btns: dict[str, ColorButton] = {}

        for row, (lbl, key) in enumerate(zip(labels, keys)):
            grid.addWidget(QLabel(lbl), row, 0)
            btn = ColorButton(self._style[key])
            btn.color_changed.connect(lambda c, k=key: self._on_color(k, c))
            grid.addWidget(btn, row, 1, Qt.AlignmentFlag.AlignRight)
            self._color_btns[key] = btn

        root.addLayout(grid)

        # 투명도 슬라이더
        root.addWidget(QLabel("투명도"))
        slider_row = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(40, 255)
        self._opacity_slider.setValue(self._style["opacity"])
        self._opacity_slider.valueChanged.connect(self._on_opacity)
        self._opacity_label = QLabel(f"{int(self._style['opacity'] / 255 * 100)}%")
        self._opacity_label.setFixedWidth(36)
        self._opacity_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        slider_row.addWidget(self._opacity_slider)
        slider_row.addWidget(self._opacity_label)
        root.addLayout(slider_row)

        # 미리보기
        preview_title = QLabel("미리보기")
        root.addWidget(preview_title)
        self._preview = _PreviewPopup()
        self._update_preview()
        root.addWidget(self._preview)

        # 구분선
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("color: #333344;")
        root.addWidget(line2)

        # 버튼 행
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("기본값으로")
        reset_btn.setObjectName("action")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        save_btn = QPushButton("저장")
        save_btn.setObjectName("save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _on_color(self, key: str, color: str) -> None:
        self._style[key] = color
        self._update_preview()
        self.style_changed.emit(dict(self._style))

    def _on_opacity(self, val: int) -> None:
        self._style["opacity"] = val
        pct = int(val / 255 * 100)
        self._opacity_label.setText(f"{pct}%")
        self._update_preview()
        self.style_changed.emit(dict(self._style))

    def _update_preview(self) -> None:
        self._preview.apply_style(self._style)

    def _reset(self) -> None:
        self._style = dict(DEFAULT_STYLE)
        for key, btn in self._color_btns.items():
            btn.set_color(self._style[key])
        self._opacity_slider.setValue(self._style["opacity"])
        self._update_preview()
        self.style_changed.emit(dict(self._style))

    def _save(self) -> None:
        cfg = settings_storage.load() or {}
        cfg["popup_style"] = self._style
        settings_storage.save(cfg)
        self.accept()

    def get_style(self) -> dict:
        return dict(self._style)


class _PreviewPopup(QFrame):
    """다이얼로그 안에 보이는 미리보기 위젯."""
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)
        self._buttons: list[QPushButton] = []
        samples = ["1.é", "2.è", "3.ê", "4.ë"]
        for s in samples:
            btn = QPushButton(s)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(btn)
            self._buttons.append(btn)
        self._hint = QLabel("ESC")
        layout.addWidget(self._hint)

    def apply_style(self, style: dict) -> None:
        opacity  = style.get("opacity", 235)
        bg       = _hex_with_opacity(style.get("bg_color",     "#18181c"), opacity)
        btn_bg   = style.get("btn_color",    "#ffffff12")
        text     = style.get("text_color",   "#f0f0f0")
        border   = style.get("border_color", "#ffffff1e")

        self.setStyleSheet(f"""
            QFrame {{
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
                font-size: 15px;
                font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
                min-width: 34px;
            }}
            QLabel {{
                color: {text};
                opacity: 0.4;
                font-size: 10px;
                background: transparent;
                border: none;
            }}
        """)