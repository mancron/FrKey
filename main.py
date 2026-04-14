# main.py
import sys
import threading
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui     import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore    import Qt

import settings_storage
from setup_wizard  import SetupWizard
from popup_window  import PopupWindow
from hook_manager  import HookManager


def _make_tray_icon() -> QIcon:
    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(90, 130, 255))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 14, 14)
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "é")
    p.end()
    return QIcon(px)


def run_app(settings: dict) -> None:
    """설정이 확정된 후 메인 앱 실행."""
    app = QApplication.instance()

    popup        = PopupWindow()
    hook_manager = HookManager(popup, settings)

    # 트레이 메뉴
    tray = QSystemTrayIcon(_make_tray_icon(), parent=app)
    key_name = settings.get("trigger_label", "설정된 키")
    tray.setToolTip(f"Accent Input  |  트리거: {key_name}")

    menu = QMenu()

    info = menu.addAction(f"트리거 키: {key_name}")
    info.setEnabled(False)
    menu.addSeparator()

    config_action = menu.addAction("설정 (키 변경)")
    quit_action   = menu.addAction("종료")

    def open_settings():
        hook_manager.stop()
        wiz = SetupWizard(is_reconfig=True)
        if wiz.exec() == SetupWizard.DialogCode.Accepted:
            new_settings = settings_storage.load()
            if new_settings:
                # 새 설정으로 훅 재시작
                hook_manager.update_settings(new_settings)
                new_name = new_settings.get("trigger_label", "설정된 키")
                tray.setToolTip(f"Accent Input  |  트리거: {new_name}")
                info.setText(f"트리거 키: {new_name}")
                hook_thread = threading.Thread(
                    target=hook_manager.start, daemon=True, name="HookThread"
                )
                hook_thread.start()
        else:
            # 취소 시 기존 설정으로 재시작
            hook_thread = threading.Thread(
                target=hook_manager.start, daemon=True, name="HookThread"
            )
            hook_thread.start()

    config_action.triggered.connect(open_settings)
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()
    tray.showMessage(
        "Accent Input",
        f"실행 중  |  트리거: {key_name}",
        QSystemTrayIcon.MessageIcon.Information,
        2500,
    )

    # 훅 스레드 시작
    hook_thread = threading.Thread(
        target=hook_manager.start, daemon=True, name="HookThread"
    )
    hook_thread.start()
    app.aboutToQuit.connect(hook_manager.stop)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = settings_storage.load()

    if settings is None:
        # ── 첫 실행: 마법사 표시 ──────────────────────────
        wiz = SetupWizard()
        if wiz.exec() != SetupWizard.DialogCode.Accepted:
            sys.exit(0)   # 마법사 취소 시 종료
        settings = settings_storage.load()
        if not settings:
            sys.exit(0)

    run_app(settings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()