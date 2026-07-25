from helpers import response_checker
from logger import log

def select_base_path(self, payload):
    # 注意:
    # Flaskを起動しているPC側にフォルダ選択ダイアログが出ます。
    try:
        import tkinter as tk
        from tkinter import filedialog
        current_path = payload.get("current_path") or ""

        root = tk.Tk()
        root.withdraw()
        root.update()
        root.attributes("-topmost", True)

        initialdir = current_path if current_path and Path(current_path).exists() else "C:/"

        selected = filedialog.askdirectory(
            parent=root,
            title="LOCAL_FLASK_SERVER のフォルダを選択",
            initialdir=initialdir,
        )

        root.destroy()

        return response_checker._json_ok(base_path=selected or "")
    except Exception as exc:
        return response_checker._json_error(f"フォルダ選択に失敗しました: {exc}", status=500)
    
def open_system_yaml(self, payload):
    base_path = payload.get("base_path") or ""

    try:
        if not base_path:
            return response_checker._json_error("ベースパスが未設定です。", status=400)

        full_path = Path(base_path) / "files" / "settings" / "system_settings.yaml"

        if not full_path.exists() or not full_path.is_file():
            return response_checker._json_error("ファイル読み込み失敗", status=404, full_path=str(full_path))
        
        os.startfile(str(full_path))  # Windows専用。関連付けされたエディタで開きます。
        return response_checker._json_ok(full_path=str(full_path))
    except Exception as exc:
        import traceback
        traceback.print_exc()          # ←追加
        log.info(repr(exc))               # ←追加
        return response_checker._json_error(
            f"ファイル読み込み失敗: {exc}",
            status=500,
            full_path=str(full_path)
        )