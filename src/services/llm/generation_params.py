# generation_params.py
"""
モデルに送る内容（メッセージと生成の設定）を1つにまとめる。

生成の設定（温度、最大トークン数など）はコードに書かず、
files/settings/generation.yaml から読む。優先順位は次のとおり。

    プロンプトのYAMLの params  >  generation.yaml の用途ごとの欄  >  generation.yaml の default  >  下の BUILTIN

書き方と項目の意味は generation.yaml の先頭のコメント、仕様は docs/spec/prompts.md を参照。
"""
import os
from typing import Any, Dict, List, Optional

import yaml

from config import config
from logger import log

# generation.yaml が無い・読めない・項目が欠けているときに使う値
BUILTIN = {
    "temperature": 0.5,
    "top_p": 0.9,
    "top_k": 0,
    "repeat_penalty": 1.1,
    "max_tokens": 800,
}

_cache: Dict[str, Any] = {"mtime": None, "data": {}}


def _settings_path():
    return config.SETTINGS_DIR / "generation.yaml"


# generation.yaml を読む。書き換えられていたら読み直す（サーバーの再起動は不要）
def _load_settings() -> Dict[str, Any]:
    path = _settings_path()

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        if _cache["mtime"] != "missing":
            log.info(f"[WARN] {path} がありません。組み込みの値を使います。")
            _cache["mtime"] = "missing"
            _cache["data"] = {}
        return _cache["data"]

    if mtime == _cache["mtime"]:
        return _cache["data"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("最上位は「用途: 設定」の形にしてください")
    except Exception as e:
        # 書きかけで壊れていても止めない。直前に読めた内容（無ければ組み込みの値）で続ける
        log.info(f"[WARN] {path} を読めませんでした。直前の設定を使います: {type(e).__name__}: {e}")
        _cache["mtime"] = mtime
        return _cache["data"]

    _cache["mtime"] = mtime
    _cache["data"] = data
    return data


def _section(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    value = data.get(name)
    return value if isinstance(value, dict) else {}


# 用途（memory / judge / chat など）の生成の設定を返す。
# prompt_params には、プロンプトのYAMLの params を渡す（無ければ None）
def get_generation_params(task_type: str, prompt_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = _load_settings()

    params = dict(BUILTIN)
    params.update(_section(data, "default"))
    params.update(_section(data, task_type))

    if isinstance(prompt_params, dict):
        params.update(prompt_params)

    return params


# モデルへ送る内容を組み立てる。ModelHandlingService.send_message にそのまま渡す。
#
#   messages     : [{"role": ..., "content": ...}] の形で渡す場合
#   user_content : 本文を文字列で渡す場合（user のメッセージ1つになる）
#   prompt_data  : プロンプトのYAMLを読んだ辞書。params があれば生成の設定を上書きする
def build_send_parameters(
    task_type: str,
    messages: Optional[List[Dict[str, str]]] = None,
    system_prompt: str = "",
    user_content: Optional[str] = None,
    prompt_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    if messages is None:
        messages = [{"role": "user", "content": user_content or ""}]

    prompt_params = prompt_data.get("params") if isinstance(prompt_data, dict) else None

    parameters = {
        "task_type": task_type,
        "prompt_messages": messages,
        "system_prompt": system_prompt or "",
        # 打ち切りの文字列は、形式に応じて llm_service 側で付ける。ここには足したいものだけ入れる
        "stop": [],
        # <think> を禁止する方法は使わない（docs/spec/prompts.md）
        "logit_bias": None,
    }
    parameters.update(get_generation_params(task_type, prompt_params))

    return parameters
