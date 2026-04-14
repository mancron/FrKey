# settings_storage.py
# 설정을 %APPDATA%/AccentInput/settings.json 에 저장/불러오기

import json
import os
from pathlib import Path

APP_NAME    = "AccentInput"
SETTINGS_DIR  = Path(os.environ.get("APPDATA", "~")) / APP_NAME
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT_SETTINGS: dict = {
    "trigger_vk":         None,   # int | None
    "trigger_appcommand": None,   # int | None
    "trigger_label":      "",     # 사람이 읽을 수 있는 키 이름
}


def load() -> dict | None:
    """저장된 설정 반환. 없으면 None."""
    if not SETTINGS_FILE.exists():
        return None
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # 최소 유효성: 둘 다 None이면 미설정으로 간주
        if data.get("trigger_vk") is None and data.get("trigger_appcommand") is None:
            return None
        return data
    except Exception:
        return None


def save(settings: dict) -> None:
    """설정 저장."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def delete() -> None:
    """설정 삭제 (재설정 시 사용)."""
    if SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()