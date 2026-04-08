# main.py
# 진입점: PyQt6 이벤트 루프 + 시스템 트레이 + 훅 스레드 시작

import sys
import threading
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui     import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore    import Qt

from popup_window import PopupWindow
from hook_manager import HookManager


def _make_tray_icon() -> QIcon:
    """16×16 트레이 아이콘 동적 생성 (의존 파일 없음)."""
    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # 배경 원
    p.setBrush(QColor(90, 130, 255))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 14, 14)
    # 'é' 글자
    p.setPen(QColor(255, 255, 255))
    f = QFont("Segoe UI", 7, QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "é")
    p.end()
    return QIcon(px)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # 트레이 앱이므로 창 닫아도 유지

    # ── 시스템 트레이 ────────────────────────────
    tray = QSystemTrayIcon(_make_tray_icon(), parent=app)
    tray.setToolTip("Accent Input Helper\n한자 키로 성조 문자 입력")

    menu = QMenu()
    about_action = menu.addAction("Accent Input Helper v1.0")
    about_action.setEnabled(False)
    menu.addSeparator()

    info_action = menu.addAction("사용법: 알파벳 입력 후 [한자] 키")
    info_action.setEnabled(False)
    menu.addSeparator()

    quit_action = menu.addAction("종료")
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()
    tray.showMessage(
        "Accent Input Helper",
        "실행 중입니다. a/e/i/o/u 입력 후 [한자] 키를 누르세요.",
        QSystemTrayIcon.MessageIcon.Information,
        3000,
    )

    # ── 팝업 + 훅 초기화 ─────────────────────────
    popup        = PopupWindow()
    hook_manager = HookManager(popup)

    hook_thread = threading.Thread(
        target=hook_manager.start,
        daemon=True,
        name="KeyboardHookThread",
    )
    hook_thread.start()

    app.aboutToQuit.connect(hook_manager.stop)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
