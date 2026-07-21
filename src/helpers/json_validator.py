import jsondef save_json_file(file_path: Path, data: Dict) -> bool:
    """
    JSONファイルを保存するヘルパー関数
    - ディレクトリがなければ自動作成
    - UTF-8で保存（日本語対応）
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[FILE] JSON保存完了: {file_path.name}")
        return True
    except Exception as e:
        print(f"[ERROR] JSON保存失敗 {file_path}: {e}")
        return False
