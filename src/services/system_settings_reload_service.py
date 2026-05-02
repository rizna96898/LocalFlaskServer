import os
from config import config

last_mtime = 0

def SystemSettingsReloadCheckService():
    global last_mtime

    settings_path = config.SETTINGS_DIR / "system_settings.yaml"
    #yamlの更新時チェック
    mtime = os.path.getmtime(settings_path)

    if mtime != last_mtime:
        print("変更がある為読み直します")
        config.reload()
        last_mtime = mtime