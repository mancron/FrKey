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
from style_dialog  import StyleDialog, DEFAULT_STYLE


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
    app = QApplication.instance()

    popup        = PopupWindow()
    hook_manager = HookManager(popup, settings)

    # 저장된 팝업 스타일 즉시 적용
    saved_style = settings.get("popup_style", DEFAULT_STYLE)
    popup.apply_popup_style(saved_style)

    tray     = QSystemTrayIcon(_make_tray_icon(), parent=app)
    key_name = settings.get("trigger_label", "설정된 키")
    tray.setToolTip(f"Accent Input  |  트리거: {key_name}")

    menu = QMenu()

    info = menu.addAction(f"트리거 키: {key_name}")
    info.setEnabled(False)
    menu.addSeparator()

    style_action  = menu.addAction("팝업 스타일 설정")
    config_action = menu.addAction("트리거 키 변경")
    menu.addSeparator()
    quit_action   = menu.addAction("종료")

    # ── 스타일 설정 ─────────────────────────────────────────
    def open_style():
        current_cfg   = settings_storage.load() or {}
        current_style = current_cfg.get("popup_style", DEFAULT_STYLE)
        dlg = StyleDialog(current_style)
        # 실시간 미리보기: 다이얼로그에서 바꿀 때마다 실제 팝업에도 반영
        dlg.style_changed.connect(popup.apply_popup_style)
        if dlg.exec() == StyleDialog.DialogCode.Accepted:
            popup.apply_popup_style(dlg.get_style())
        else:
            # 취소 시 원래 스타일 복원
            popup.apply_popup_style(current_style)

    style_action.triggered.connect(open_style)

    # ── 트리거 키 변경 ───────────────────────────────────────
    def open_key_settings():
        hook_manager.stop()
        wiz = SetupWizard(is_reconfig=True)
        if wiz.exec() == SetupWizard.DialogCode.Accepted:
            new_settings = settings_storage.load()
            if new_settings:
                hook_manager.update_settings(new_settings)
                new_name = new_settings.get("trigger_label", "설정된 키")
                tray.setToolTip(f"Accent Input  |  트리거: {new_name}")
                info.setText(f"트리거 키: {new_name}")
        threading.Thread(target=hook_manager.start, daemon=True, name="HookThread").start()

    config_action.triggered.connect(open_key_settings)
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()
    tray.showMessage(
        "Accent Input",
        f"실행 중  |  트리거: {key_name}",
        QSystemTrayIcon.MessageIcon.Information,
        2500,
    )

    threading.Thread(target=hook_manager.start, daemon=True, name="HookThread").start()
    app.aboutToQuit.connect(hook_manager.stop)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = settings_storage.load()

    if settings is None:
        wiz = SetupWizard()
        if wiz.exec() != SetupWizard.DialogCode.Accepted:
            sys.exit(0)
        settings = settings_storage.load()
        if not settings:
            sys.exit(0)

    run_app(settings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()