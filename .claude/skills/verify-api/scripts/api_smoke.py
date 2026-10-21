"""全APIを一通り呼ぶスモークテスト。本物のデータには触れない。

    py -3 .claude/skills/verify-api/scripts/api_smoke.py

確かめること:
- レスポンスの形（成功は ok: true、失敗は ok: false + message + HTTPステータス）
- 設定系（テンプレート、世界・キャラクターの保存と読み込み、画像）
- セッション系（一覧、作成、履歴、発言の失敗と送り直し、削除）
- 画像（キャラクター／プレイヤーの保存と読み込み、セッションに退避した画像）

呼ばないもの:
- /settings/select_base_path と /settings/open_system_yaml の成功時
  （サーバーを動かしているPCにダイアログやエディタが開いてしまうため）
- モデルの実際の応答（偽物に差し替えている）
"""
import io
import sys
from urllib.parse import quote

import _env

_env.utf8_stdout()
_env.run_in_venv(_env.default_sandbox())

import sandbox  # noqa: E402  (venv に入ってから読み込む)

OLD_KEYS = ("status", "result", "error", "response", "status_code")


def main() -> int:
    box = sandbox.prepare()
    client = box.client()          # モデルサーバーには接続できない扱い
    t = sandbox.Checker()
    web = box.base_chat_path
    q = quote(web)

    worlds = box.worlds()
    characters = box.characters_with_images()
    if not worlds or not characters:
        print("世界設定、または画像を持つキャラクターが LLM_CHAT_CONSOLE に見つかりません。")
        return 1
    world_id, world = worlds[0]
    world_name = world.get("世界名", "")
    cid = characters[0]
    icon_png = (box.web / "characters" / "icon" / cid / f"{cid}.png").read_bytes()
    standing_png = (box.web / "characters" / "standing" / cid / f"{cid}_standing.png").read_bytes()
    print(f"使用するデータ: 世界={world_id} キャラクター={cid}\n")

    # ---------------------------------------------------------------- 基本
    print("# 基本・設定")
    t.api(client, "health", "get", "/health", 200, True)
    for name in ("world_include_player", "world_goal_setting", "world_parameter_setting", "player", "character"):
        t.api(client, f"テンプレート取得 {name}", "post", f"/settings/get_template_{name}_yaml", 200, True,
              ["content"], json={"base_chat_path": web})
    t.api(client, "テンプレート取得 パス未指定", "post", "/settings/get_template_player_yaml", 400, False, json={})
    t.api(client, "load_model パス未指定", "post", "/settings/load_model", 400, False, json={})
    t.api(client, "load_model 不正パス", "post", "/settings/load_model", 404, False, json={"base_path": web + "_x"})
    # モデルロードは、モデルサーバー(src/server.py)に読み直しを頼む（モデルサーバー自体は model_server_check.py で確かめる）
    t.api(client, "load_model モデルサーバー停止中 → 503", "post", "/settings/load_model", 503, False,
          json={"base_path": str(box.server)})
    body = t.api(box.client(llm="x"), "load_model", "post", "/settings/load_model", 200, True, ["model_name"],
                 json={"base_path": str(box.server)})
    t.check("  読み込んだモデルの名前が返る", body.get("model_name") == "fake.gguf", body)
    client = box.client()                                # 以降は、モデルに接続できない扱いに戻す
    t.api(client, "open_system_yaml パス未指定", "post", "/settings/open_system_yaml", 400, False, json={})
    t.api(client, "open_system_yaml 不正パス", "post", "/settings/open_system_yaml", 404, False,
          json={"base_path": web + "_x"})
    t.api(client, "check_stability GET", "get", "/v1/chat/check_stability", 200, True)
    t.api(client, "check_stability POST", "post", "/v1/chat/check_stability", 200, True, json={})

    # ---------------------------------------------------------------- 世界・キャラクター設定
    print("\n# 世界・キャラクター設定")
    import yaml

    def dump(value):
        return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)

    t.api(client, "世界設定の読み込み（項目名は保存と同じ）", "post", "/settings/load_world_settings", 200, True,
          ["include_data", "goal_data", "parameter_data", "past", "current", "future", "purpose", "supplement", "start_message"],
          json={"base_chat_path": web, "world_id": world_id})
    t.api(client, "キャラクター設定の読み込み", "post", "/settings/load_character_settings", 200, True,
          ["character_id", "character_name", "character_info"], json={"base_chat_path": web, "character_id": cid})
    t.api(client, "世界設定の保存", "post", "/settings/save_world_setting", 200, True, ["path"], json={
        "base_chat_path": web, "world_id": "zz_verify", "world_name": "検証用の世界", "purpose": "p", "supplement": "s",
        "include_data": dump(world["登場人物"]), "goal_data": dump(world["シナリオの目標"]),
        "parameter_data": dump(world["シナリオパラメータ"]),
        "past": "", "current": "いま", "future": "", "start_message": "開始"})
    t.check("  保存した世界YAMLがある", (box.web / "worlds" / "settings" / "zz_verify_world.yaml").exists())
    two_players = dict(world["登場人物"])
    two_players["世界の登場人物"] = list(two_players["世界の登場人物"]) + [
        next(p for p in two_players["世界の登場人物"] if p.get("参照種別") == "player")]
    t.api(client, "世界設定の保存 player が2人 → 400", "post", "/settings/save_world_setting", 400, False, json={
        "base_chat_path": web, "world_id": "zz_two_players", "world_name": "x", "include_data": dump(two_players),
        "goal_data": dump(world["シナリオの目標"]), "parameter_data": dump(world["シナリオパラメータ"])})
    no_ref_id = dict(world["登場人物"])
    no_ref_id["世界の登場人物"] = list(no_ref_id["世界の登場人物"]) + [
        {"参照種別": "inline", "参照ID": None, "表示名": "名無し", "役割": "mob"}]
    t.api(client, "世界設定の保存 inline の参照IDなし → 400", "post", "/settings/save_world_setting", 400, False, json={
        "base_chat_path": web, "world_id": "zz_no_ref_id", "world_name": "x", "include_data": dump(no_ref_id),
        "goal_data": dump(world["シナリオの目標"]), "parameter_data": dump(world["シナリオパラメータ"])})
    t.api(client, "世界設定の保存 ID不正", "post", "/settings/save_world_setting", 400, False,
          json={"base_chat_path": web, "world_id": "a-b", "world_name": "x"})
    t.api(client, "世界設定の読み込み 無いID → 404", "post", "/settings/load_world_settings", 404, False,
          json={"base_chat_path": web, "world_id": "no_such_world"})
    t.api(client, "キャラクター設定の読み込み 無いID → 404", "post", "/settings/load_character_settings", 404, False,
          json={"base_chat_path": web, "character_id": "no_such_character"})

    # 一覧はフォルダの中身から作る（→ docs/spec/api.md「一覧」）
    pid = next(p.get("参照ID") for p in world["登場人物"]["世界の登場人物"] if p.get("参照種別") == "player")
    for kind, wanted in (("world", "zz_verify"), ("character", cid), ("player", pid)):
        body = t.api(client, f"一覧 {kind}", "post", "/settings/list_settings", 200, True, ["items"],
                     json={"base_chat_path": web, "kind": kind})
        items = body.get("items", [])
        t.check(f"  {wanted} が一覧にあり、名前が付いている",
                any(i.get("id") == wanted and i.get("name") for i in items), items)
    body = t.api(client, "一覧 world の名前は 世界名", "post", "/settings/list_settings", 200, True, ["items"],
                 json={"base_chat_path": web, "kind": "world"})
    t.check("  保存した世界の名前", any(i == {"id": "zz_verify", "name": "検証用の世界"} for i in body.get("items", [])))
    t.api(client, "一覧 kind 不正 → 400", "post", "/settings/list_settings", 400, False, json={"base_chat_path": web, "kind": "x"})
    t.api(client, "一覧 base_chat_path なし → 400", "post", "/settings/list_settings", 400, False, json={"kind": "world"})
    t.api(client, "一覧 base_chat_path が無いフォルダ → 404", "post", "/settings/list_settings", 404, False,
          json={"base_chat_path": web + "_x", "kind": "world"})

    body = t.api(client, "プレイヤー設定の読み込み", "post", "/settings/load_player_settings", 200, True,
                 ["player_id", "player_name", "player_info"], json={"base_chat_path": web, "player_id": pid})
    t.check("  ファイルの中身が返る", body.get("player_id") == pid and "名前" in (body.get("player_info") or ""), body.get("player_id"))
    t.api(client, "プレイヤー設定の読み込み 無いID → 404", "post", "/settings/load_player_settings", 404, False,
          json={"base_chat_path": web, "player_id": "no_such_player"})
    t.api(client, "プレイヤー設定の読み込み ID不正 → 400", "post", "/settings/load_player_settings", 400, False,
          json={"base_chat_path": web, "player_id": "../x"})

    # ---------------------------------------------------------------- 画像
    print("\n# 画像の保存と読み込み")

    def save_image(name, status, expect_file=None, with_file=True, **form):
        data = dict(form)
        if with_file:
            data["file"] = (io.BytesIO(icon_png), "a.png")
        body = t.api(client, name, "post", "/settings/save_image", status, status == 200,
                     data=data, content_type="multipart/form-data")
        if expect_file:
            path = box.web / expect_file
            t.check(f"  {expect_file} に保存された", path.exists() and path.read_bytes() == icon_png)
        return body

    save_image("キャラクターのアイコン", 200, "characters/icon/zz_c/zz_c.png",
               base_chat_path=web, owner_type="character", owner_id="zz_c", image_type="icon")
    save_image("キャラクターの立ち絵（owner_type 省略）", 200, "characters/standing/zz_c/zz_c_standing.png",
               base_chat_path=web, owner_id="zz_c", image_type="standing")
    save_image("プレイヤーのアイコン", 200, "players/icon/zz_p/zz_p.png",
               base_chat_path=web, owner_type="player", owner_id="zz_p", image_type="icon")
    save_image("プレイヤーの立ち絵", 200, "players/standing/zz_p/zz_p_standing.png",
               base_chat_path=web, owner_type="player", owner_id="zz_p", image_type="standing")
    save_image("base_chat_path なし", 400, owner_type="player", owner_id="zz_p", image_type="icon")
    save_image("owner_type 不正", 400, base_chat_path=web, owner_type="world", owner_id="zz_p", image_type="icon")
    save_image("image_type 不正", 400, base_chat_path=web, owner_type="player", owner_id="zz_p", image_type="thumb")
    save_image("ID なし", 400, base_chat_path=web, owner_type="player", image_type="icon")
    save_image("ID に ../ を含む", 400, base_chat_path=web, owner_type="player", owner_id="../../evil", image_type="icon")
    save_image("ファイルなし", 400, with_file=False,
               base_chat_path=web, owner_type="player", owner_id="zz_p", image_type="icon")
    t.check("  サンドボックスの外に書き込まれていない", not list(box.root.rglob("evil*")))

    def load_image(name, url, status, expect=None):
        response = client.get(url)
        ok = response.status_code == status
        if status == 200:
            ok = ok and response.data == expect
        else:
            ok = ok and (response.get_json(silent=True) or {}).get("ok") is False
        t.check(name, ok, f"status {response.status_code}")

    load_image("読み込み キャラクターのアイコン", f"/settings/load_image/icon/zz_c?base_chat_path={q}", 200, icon_png)
    load_image("読み込み プレイヤーのアイコン", f"/settings/load_image/icon/zz_p?owner_type=player&base_chat_path={q}", 200, icon_png)
    load_image("読み込み プレイヤーをキャラクターとして → 404", f"/settings/load_image/icon/zz_p?base_chat_path={q}", 404)
    load_image("読み込み 存在しないID → 404", f"/settings/load_image/icon/nobody?base_chat_path={q}", 404)
    load_image("読み込み base_chat_path なし → 400", "/settings/load_image/icon/zz_c", 400)
    load_image("読み込み image_type 不正 → 400", f"/settings/load_image/thumb/zz_c?base_chat_path={q}", 400)

    # ---------------------------------------------------------------- セッション
    print("\n# セッション")
    t.check("開始時点で sessions_list.yaml は無い", not (box.server / "files" / "systems" / "sessions_list.yaml").exists())
    t.api(client, "一覧 world_id なし", "post", "/load_session_list", 400, False, json={})
    t.api(client, "一覧（空）", "post", "/load_session_list", 200, True, ["sessions"], json={"world_id": world_id})
    t.api(client, "world_start world_id なし", "post", "/world_start", 400, False, json={})
    t.api(client, "world_start world_name なし", "post", "/world_start", 400, False, json={"world_id": world_id})
    t.api(client, "world_start", "post", "/world_start", 200, True, ["world_id", "world_name", "sessions"],
          json={"world_id": world_id, "world_name": world_name})

    body = t.api(client, "chat_startup", "post", "/chat_startup", 200, True,
                 ["session_id", "world_id", "world_name", "display_name", "created_at", "updated_at"],
                 json={"world_id": world_id, "base_chat_path": web})
    sid = body.get("session_id", "")
    char_files = sorted(p.name for p in (box.sessions / sid / "character").glob("*.yaml"))
    t.check("  登場人物の設定は全員 {ID}_setting.yaml の名前でコピーされる（inline も）",
            bool(char_files) and all(n.endswith("_setting.yaml") for n in char_files), char_files)
    listed = t.api(client, "一覧（1件）", "post", "/load_session_list", 200, True, ["sessions"], json={"world_id": world_id})
    t.check("  作ったセッションが一覧にある", any(s.get("session_id") == sid for s in listed.get("sessions", [])))
    started = client.post("/world_start", json={"world_id": world_id, "world_name": world_name}).get_json() or {}
    t.check("  世界を選んだとき（world_start）も、同じ一覧が返る", started.get("sessions") == listed.get("sessions"))
    t.api(client, "selected_session", "post", "/selected_session", 200, True, ["session_id", "message_list"],
          json={"session_id": sid})

    # セッションは /chat_startup で作ってあるはず。無いIDなら何も作らずに断る
    t.api(client, "new_chat 無いセッション → 404", "post", "/new_chat", 404, False, json={"session_id": "no_such_session"})
    t.check("  フォルダを作らない", not (box.sessions / "no_such_session").exists())
    t.api(client, "new_chat session_id なし → 400", "post", "/new_chat", 400, False, json={})
    t.api(client, "new_chat session_id 不正 → 400", "post", "/new_chat", 400, False, json={"session_id": "../x"})

    body = t.api(client, "new_chat", "post", "/new_chat", 200, True, ["session_id", "line_id", "message", "icon_data"],
                 json={"session_id": sid})
    t.check("  開始メッセージが世界設定と一致", body.get("message") == world.get("開始メッセージ"))
    t.check("  裏の記憶生成スレッドが終わる", box.wait_background())
    t.check("  記憶生成がモデルへ送信しようとした", len(box.llm_calls) >= 1, f"{len(box.llm_calls)} 回")

    # モデルへ送る形。形式がモデルと合っていないと空の返事になるので、既定の形を固定しておく
    # （→ docs/spec/prompts.md「ローカルモデルへ送る形」）
    if box.llm_requests:
        sent = box.llm_requests[0]
        prompt = sent.get("prompt", "")
        t.check("  送る形式は ChatML（<|im_start|> で始まる）", prompt.startswith("<|im_start|>"), repr(prompt[:60]))
        t.check("  返事の出だしに空の思考ブロックを置いている",
                prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n"), repr(prompt[-60:]))
        t.check("  古い形式（### Instruction:）が混ざっていない", "### Instruction:" not in prompt)
        t.check("  打ち切りの文字列は <|im_end|>", sent.get("stop") == ["<|im_end|>"], sent.get("stop"))
        t.check("  <think> を logit_bias で禁止していない", not sent.get("logit_bias"), sent.get("logit_bias"))

    def history():
        body = client.post("/selected_session", json={"session_id": sid}).get_json() or {}
        return [(m.get("line_id"), m.get("icon_data", {}).get("character_id"), m.get("message"))
                for m in body.get("message_list", [])]

    # 発言に失敗したら、プレイヤーの発言も履歴に残さない（→ docs/spec/chat-flow.md「発言する」）
    t.api(client, "chat（モデルサーバー停止中）→ 500", "post", "/chat", 500, False,
          json={"session_id": sid, "message": "こんにちは"})
    t.check("  失敗した発言は履歴に残らない（開始メッセージだけ）", len(history()) == 1, history())
    status = client.post("/re_chat", json={"session_id": sid}).status_code
    t.check("/re_chat は無い（再送ボタンは無くした）→ 404", status == 404, f"status {status}")

    # 失敗したあと、同じ発言を送り直せば、発言と返事が続きの番号で入る
    # 発言者は実際の人物（→ docs/spec/chat-flow.md「発言する」Q53・Q54）
    people = [x for x in world["登場人物"]["世界の登場人物"] if x.get("参照種別") not in (None, "null")]
    mains = [x["参照ID"] for x in people if x.get("参照種別") == "character"]
    others = [x["参照ID"] for x in people if x.get("参照種別") not in ("player", "character")]
    client = box.client(llm="返事（判定できない答え）")
    before = len(box.llm_requests)
    body = t.api(client, "chat（送り直し）", "post", "/chat", 200, True, ["line_id", "message", "icon_data", "player_line_id"],
                 json={"session_id": sid, "message": "こんにちは"})
    t.check("  返事は 3 行目、プレイヤーの発言は 2 行目", (body.get("line_id"), body.get("player_line_id")) == ("3", "2"), body)
    listed_now = (client.post("/load_session_list", json={"world_id": world_id}).get_json() or {}).get("sessions", [])
    this_session = next((s for s in listed_now if s.get("session_id") == sid), {})
    t.check("  発言すると、セッション一覧の更新日時が今になり、返事にも入る",
            bool(body.get("updated_at")) and this_session.get("updated_at") == body.get("updated_at"), (body.get("updated_at"), this_session))
    t.check("  判定できなければ、返事をするのは最初のメイン", body.get("icon_data", {}).get("character_id") == mains[0], body.get("icon_data"))
    t.check("  履歴: 開始メッセージ（最初のメイン）、発言（実際のプレイヤー）、返事",
            [h[:2] for h in history()] == [("1", mains[0]), ("2", pid), ("3", mains[0])], history())
    judge = box.llm_requests[before].get("prompt", "") if len(box.llm_requests) > before else ""
    t.check("  判定プロンプトの候補に、職業が付く",
            all(f"・{x['職業']}）" in judge for x in people if x.get("参照種別") != "player" and x.get("職業")), judge[:400])
    t.check("  判定プロンプトに、世界の登場人物が入る（直書きでない）",
            all(f"{x['参照ID']}（" in judge for x in people if x.get("参照種別") != "player"), judge[:300])
    t.check("  判定プロンプトに、直前の発言（開始メッセージ）と今回の発言が入る",
            world.get("開始メッセージ", "")[:20] in judge and "こんにちは" in judge)
    t.check("  判定プロンプトに、置換前の差し込み口が残っていない",
            not any(k in judge for k in ("{characters}", "{player_message}", "{player_answer}")))
    body = t.api(client, "selected_session（役割とプレイヤー）", "post", "/selected_session", 200, True, ["message_list", "player"],
                 json={"session_id": sid})
    t.check("  履歴の各行に role が付く", [m.get("role") for m in body.get("message_list", [])] == ["main", "player", "main"],
            [m.get("role") for m in body.get("message_list", [])])
    t.check("  プレイヤーの情報が返る", body.get("player", {}).get("character_id") == pid, body.get("player"))

    # 判定で言われた相手が分かれば、その人が返事をする
    if others:
        client = box.client(llm=f"target_speakers: {others[0]}")
        body = t.api(client, "chat（言われた相手が返事をする）", "post", "/chat", 200, True, ["icon_data"],
                     json={"session_id": sid, "message": "あなたに話しています"})
        t.check(f"  返事をするのは {others[0]}", body.get("icon_data", {}).get("character_id") == others[0], body.get("icon_data"))
    # 返事と掛け合い（→ docs/spec/chat-flow.md「本番の発言の流れ」）
    if others:
        main, sub = mains[0], others[0]
        names = {x["参照ID"]: x.get("表示名") for x in people}
        names_player = names[pid]

        def saved_history():
            # 画面向けの /selected_session は10行ごとに畳むので、ファイルを直接読む
            import json as _json
            return [h.get("speaker") for h in _json.loads((box.sessions / sid / "history.json").read_text(encoding="utf-8"))]
        sent_prompts = []

        def talk_llm(prompt, attention_to=sub):
            sent_prompts.append(prompt)
            if "誰に向けた物かを判別" in prompt:
                return f"target_speakers: {main}"
            if "意識を向けている相手" in prompt:
                return f"相手: {attention_to}"
            if f"今、あなたの意識は {names_player} に" in prompt:
                return "（向き直って）\n先生、お願いします"
            if "今、あなたの意識は" in prompt:
                return "（期待）\nね、いこ？"
            if f"あなたは {names[sub]} として" in prompt:
                return "（うなずく）\nうん"
            return "（嬉しい）\nはーい"

        client = box.client(llm=talk_llm)
        before = len(saved_history())
        body = t.api(client, "chat（意識がサブに向いていれば掛け合い）", "post", "/chat", 200, True, ["messages"],
                     json={"session_id": sid, "message": "いらっしゃいませ"})
        got = [(m.get("icon_data", {}).get("character_id"), m.get("message")) for m in body.get("messages", [])]
        t.check("  返事 → 話しかけ → 相手の返事 → プレイヤーへの向き直り の4行",
                got == [(main, "（嬉しい）\nはーい"), (main, "（期待）\nね、いこ？"), (sub, "（うなずく）\nうん"),
                        (main, "（向き直って）\n先生、お願いします")], got)
        t.check("  1件目は今までどおり line_id・message でも返る", body.get("message") == "（嬉しい）\nはーい")
        chat_logs = [x.name for x in sorted((box.server / "logs" / sid).glob("*.txt"))] if (box.server / "logs" / sid).exists() else []
        t.check("  発言の記録（判定・返事・意識・話しかけ）も、そのセッションのフォルダに入る",
                all(any(step in n for n in chat_logs) for step in ("判定", "返事_", "意識_", "話しかけ_")), chat_logs[-8:])
        t.check("  履歴に、発言 → 4行の順で入る", saved_history()[before:] == [pid, main, main, sub, main], saved_history()[before:])
        box.wait_background(20)
        reply_prompt = next((q for q in sent_prompts if f"あなたは {names[main]} として" in q and "今、あなたの意識は" not in q), "")
        t.check("  返事のプロンプトに、記憶・これまでの会話・プレイヤーの発言が入る",
                "#今の記憶" in reply_prompt and "#これまでの会話" in reply_prompt and "いらっしゃいませ" in reply_prompt
                and not any(k in reply_prompt for k in ("{character_name}", "{character_info}", "{partner_message}")), reply_prompt[-400:])
        attention_prompt = next((q for q in sent_prompts if "意識を向けている相手" in q), "")
        t.check("  意識の確認に、直前までの記憶（記憶の無いときは関係性）が入る",
                "今の記憶（直前まで）" in attention_prompt and "関係性" in attention_prompt
                and "{character_memory}" not in attention_prompt, attention_prompt[-500:])
        sub_prompt = next((q for q in sent_prompts if f"あなたは {names[sub]} として" in q), "")
        t.check("  サブの返事のプロンプトに、話しかけられた一言と関係性が入る", "ね、いこ？" in sub_prompt and "関係性" in sub_prompt, sub_prompt[-400:])
        # 同じ言葉を繰り返させないため、話しかけには返事を、向き直りには話しかけを「直前のあなたの発言」として渡す
        opener_prompt = next((q for q in sent_prompts if "今、あなたの意識は" in q and f"意識は {names_player} に" not in q), "")
        closing_prompt = next((q for q in sent_prompts if f"今、あなたの意識は {names_player} に" in q), "")
        t.check("  話しかけ・向き直りのプロンプトに、自分の直前の発言が入る",
                "#直前のあなたの発言" in opener_prompt and opener_prompt.split("#直前のあなたの発言")[1].count("はーい") == 1
                and closing_prompt.split("#直前のあなたの発言")[-1].count("ね、いこ？") == 1
                and "{previous_line}" not in opener_prompt + closing_prompt, closing_prompt[-300:])

        client = box.client(llm=lambda prompt: talk_llm(prompt, attention_to=pid))
        body = t.api(client, "chat（意識がプレイヤーなら掛け合いなし）", "post", "/chat", 200, True, ["messages"],
                     json={"session_id": sid, "message": "どうぞ"})
        t.check("  返事だけの1行", len(body.get("messages", [])) == 1, body.get("messages"))

        def broken_attention(prompt):
            if "意識を向けている相手" in prompt:
                raise RuntimeError("意識の確認だけ失敗")
            return talk_llm(prompt)

        client = box.client(llm=broken_attention)
        body = t.api(client, "chat（意識の確認に失敗しても返事は返す）", "post", "/chat", 200, True, ["messages"],
                     json={"session_id": sid, "message": "大丈夫？"})
        t.check("  返事だけの1行", len(body.get("messages", [])) == 1, body.get("messages"))

        # パーティー: 相談と、掛け合いの相手（→ docs/spec/chat-flow.md「発言1回分の流れ」2a・4）
        wm_path = box.sessions / sid / "world_memory.yaml"
        wm_saved = wm_path.read_bytes() if wm_path.exists() else None

        def set_party(member_ids):
            wm_path.write_text(yaml.safe_dump({"現在の状態": {"パーティー一覧": [
                {"名前": "テストの組", "メンバー一覧": [{"キャラクターID": i, "名前": names.get(i, i)} for i in member_ids]}]}},
                allow_unicode=True), encoding="utf-8")

        party_prompts = []

        def party_llm(prompt, consult_to="null"):
            party_prompts.append(prompt)
            if "だれかに相談するか" in prompt:
                return f"相談: {consult_to}"
            if "に相談します。" in prompt:
                return "（迷って）\nどうしよう？"
            return talk_llm(prompt, attention_to=sub)

        set_party([main, sub])
        body = t.api(box.client(llm=lambda q: party_llm(q, consult_to=sub)), "chat（同じパーティーの人に相談してから答える）",
                     "post", "/chat", 200, True, ["messages"], json={"session_id": sid, "message": "二つの方法がありますが、どうされますか？"})
        got = [(m.get("icon_data", {}).get("character_id"), m.get("message")) for m in body.get("messages", [])]
        t.check("  相談 → 相手の返事 → プレイヤーへの返事 の3行",
                got == [(main, "（迷って）\nどうしよう？"), (sub, "（うなずく）\nうん"), (main, "（嬉しい）\nはーい")], got)
        t.check("  相談したときは、意識の確認をしない", not any("意識を向けている相手」を特定" in q for q in party_prompts))
        check_prompt = next((q for q in party_prompts if "だれかに相談するか" in q), "")
        final_prompt = [q for q in party_prompts if f"あなたは {names[main]} として" in q and "に相談します。" not in q][-1:]
        t.check("  相談の確認に、相談できる相手とパーティーが入る",
                f"{sub}（" in check_prompt.split("相談できる相手:")[-1] and "テストの組" in check_prompt and "{mates}" not in check_prompt, check_prompt[-500:])
        t.check("  プレイヤーへの返事のプロンプトに、相談のやり取りが入る", bool(final_prompt) and "どうしよう？" in final_prompt[0], final_prompt)

        party_prompts.clear()
        body = t.api(box.client(llm=party_llm), "chat（相談しない → 返事のあと、同じパーティーの人と掛け合い）",
                     "post", "/chat", 200, True, ["messages"], json={"session_id": sid, "message": "こんにちは"})
        t.check("  返事 → 話しかけ → 相手の返事 → 向き直り の4行", len(body.get("messages", [])) == 4, body.get("messages"))
        attention = next((q for q in party_prompts if "意識を向けている相手」を特定" in q), "")
        t.check("  意識の確認に、パーティー一覧が入る", "テストの組" in attention and "{parties}" not in attention, attention[-400:])

        set_party([main, "nobody"])
        party_prompts.clear()
        body = t.api(box.client(llm=party_llm), "chat（意識の相手が同じパーティーでなければ掛け合わない）",
                     "post", "/chat", 200, True, ["messages"], json={"session_id": sid, "message": "こんにちは"})
        t.check("  返事だけの1行", len(body.get("messages", [])) == 1, body.get("messages"))
        t.check("  その場に同じパーティーの人がいなければ、相談の確認もしない", not any("だれかに相談するか" in q for q in party_prompts))

        if wm_saved is None:
            wm_path.unlink()
        else:
            wm_path.write_bytes(wm_saved)
    client = box.client()                                # 以降は、モデルに接続できない扱いに戻す

    # ---------------------------------------------------------------- 初期記憶の生成（偽モデルで完走させる）
    print("\n# 初期記憶の生成")
    # 段階ごとに、それらしい返事を返す偽モデル。送られるたびに、その時点の進み具合を控える
    watched = {"sid": "", "progress": []}

    def watching_llm(prompt):
        path = box.sessions / watched["sid"] / "prepare_status.yaml"
        if watched["sid"] and path.exists():
            s = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            watched["progress"].append((s.get("progress_done"), s.get("progress_total"), s.get("progress_label")))
        return sandbox.scripted_llm(prompt)

    scripted = box.client(llm=watching_llm)
    before = len(box.llm_requests)
    msid = (scripted.post("/chat_startup", json={"world_id": world_id, "base_chat_path": web}).get_json() or {}).get("session_id", "")
    watched["sid"] = msid
    scripted.post("/new_chat", json={"session_id": msid})
    t.check("裏の処理が終わる", box.wait_background(60))

    # 進み具合（/session_status）。全段階 = 世界(1) + メインキャラクター1人につき7段階
    mains = sum(1 for c in world["登場人物"]["世界の登場人物"] if isinstance(c, dict) and c.get("参照種別") == "character")
    total = 1 + 7 * mains
    seen = watched["progress"]
    t.check("作成中の進み具合: 全段階の数が 1 + 7 × メイン人数", bool(seen) and all(p[1] == total for p in seen), (total, seen[:3]))
    t.check("作成中の進み具合: 終わった数は 0 から増えていき、全段階に届かない",
            bool(seen) and seen[0][0] == 0 and all(a[0] <= b[0] for a, b in zip(seen, seen[1:])) and seen[-1][0] < total,
            [p[0] for p in seen])
    t.check("作成中の進み具合: 最初は世界の記憶", bool(seen) and seen[0][2] == "世界の記憶", seen[:1])
    body = t.api(scripted, "session_status（完了）", "post", "/session_status", 200, True,
                 ["session_id", "status", "complete_stage", "progress"], json={"session_id": msid})
    t.check("  ready で、進み具合は 全段階/全段階", body.get("status") == "ready"
            and body.get("progress") == {"done": total, "total": total, "label": "完了"}, body.get("progress"))
    t.api(scripted, "session_status session_id なし → 400", "post", "/session_status", 400, False, json={})
    t.api(scripted, "session_status session_id 不正 → 400", "post", "/session_status", 400, False,
          json={"session_id": "../x"})
    t.api(scripted, "session_status 無いセッション → 404", "post", "/session_status", 404, False,
          json={"session_id": "no_such_session"})
    status = yaml.safe_load((box.sessions / msid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
    t.check("進行状態が ready（エラーなし）", status.get("status") == "ready", status)
    t.check("世界の記憶ができる", (box.sessions / msid / "world_memory.yaml").exists())
    wm = yaml.safe_load((box.sessions / msid / "world_memory.yaml").read_text(encoding="utf-8")) or {}
    t.check("世界の記憶のプレイヤーは、世界の登場人物の player（固定の名前でない）", wm.get("プレイヤーID") == pid,
            (wm.get("プレイヤーID"), wm.get("プレイヤー名")))
    memories = sorted(p.name for p in (box.sessions / msid / "character").glob("*_memory.yaml"))
    t.check("キャラクターの記憶ができる", len(memories) >= 1, memories)
    sent = box.llm_requests[before:]
    stages = ["状態と記憶を構造化", "情報抽出担当", "「居場所」を特定", "分類機", "「現在の服装」を特定",
              "「現在の所持品」を特定", "「意識を向けている相手」を特定", "「所持金」を確定"]
    missing = [s for s in stages if not any(s in q.get("prompt", "") for q in sent)]
    t.check("全段階（世界 ＋ キャラクター7段階）のプロンプトが送られる", not missing, f"送られていない段階: {missing}")
    # 組み立て方は全段階共通（header ＋ 本文 ＋ template ＋ tail_template）。要約の tail_template も送る
    summary = [q.get("prompt", "") for q in sent if "情報抽出担当" in q.get("prompt", "")]
    t.check("要約の段階に tail_template が入る", bool(summary) and all("要約結果のみを出力" in s for s in summary))

    # 生成の設定は files/settings/generation.yaml から読む（→ docs/spec/prompts.md「生成の設定」）
    wanted = yaml.safe_load(box.generation_file.read_text(encoding="utf-8")) or {}
    expect = dict(wanted.get("default") or {}, **(wanted.get("memory") or {}))
    wrong = [q for q in sent if any(q.get(k) != v for k, v in expect.items())]
    t.check("送信した設定が generation.yaml の memory の値と一致", bool(expect) and not wrong,
            f"期待 {expect} / 違うもの {len(wrong)} 件")
    # 発言のあと、裏でキャラクターの記憶を更新する（→ docs/spec/chat-flow.md「本番の発言の流れ」7）
    print("\n# 発言のあとの記憶の更新")
    mem_files = sorted((box.sessions / msid / "character").glob("*_memory.yaml"))
    if mem_files:
        mem_path = mem_files[0]
        old_mem = yaml.safe_load(mem_path.read_text(encoding="utf-8")) or {}
        updated_yaml = ("現在の状態:\n  場所: 診察室\n  状態:\n  - 診察を受けている\n  心情:\n  - 安心\n"
                        "  関係性:\n  - キャラクターID: kyuya\n    名前: 究也\n    役割: 先生\n  意識:\n  - 究也\n")
        update_prompts = []
        cast_people = [x for x in world["登場人物"]["世界の登場人物"] if x.get("参照種別") not in (None, "null")]
        main_ids = [x["参照ID"] for x in cast_people if x.get("参照種別") == "character"]
        other_ids = [x["参照ID"] for x in cast_people if x.get("参照種別") not in ("player", "character")]
        present_prompts = []
        # その場の参加者: メインが残り、圭太（others[0]）は出て行き、世界設定にいない「田中」が現れた
        present_yaml = (f"その場の参加者:\n  - キャラクターID: {main_ids[0]}\n    名前: x\n    役割: ヒロイン\n"
                        "  - キャラクターID: null\n    名前: 田中\n    役割: プレイヤーの友人\n")

        newcomer_answer = {"yaml": "呼ばれた人: null"}

        summary_prompts = []
        party_prompts = []
        # パーティー: メインと田中（名前だけで答える）が組む。プレイヤーと、登場人物にいない人は外れ、1人だけの組は消える
        party_yaml = (f"パーティー一覧:\n  - 名前: 付き添い\n    メンバー一覧:\n      - キャラクターID: {main_ids[0]}\n"
                      f"      - キャラクターID: null\n        名前: 田中\n      - キャラクターID: {pid}\n      - キャラクターID: nobody\n"
                      f"  - 名前: ひとり\n    メンバー一覧:\n      - キャラクターID: {main_ids[0]}\n")

        def update_llm(prompt):
            if "呼ばれた人・話しかけられた人" in prompt:     # 返事の前の「呼ばれた人」の確認
                return newcomer_answer["yaml"]
            if "会話の流れを記録する係" in prompt:            # あらすじの更新
                summary_prompts.append(prompt)
                return "あらすじ:\n  - 結と圭太は診察室に通された。\n  - 究也は来週の検査を約束した。\n"
            if "その場にいる人を管理するAI" in prompt:
                present_prompts.append(prompt)
                return present_yaml
            if "一緒に行動している人のまとまりを管理するAI" in prompt:   # パーティー一覧の更新
                party_prompts.append(prompt)
                return party_yaml
            if "キャラクターの状態と記憶を更新するAI" in prompt:
                update_prompts.append(prompt)
                return updated_yaml
            if "誰に向けた物かを判別" in prompt or "意識を向けている相手" in prompt:
                return "相手: null"
            return "（ほっとして）\nよろしくお願いします"

        updater = box.client(llm=update_llm)
        body = t.api(updater, "chat（記憶のあるセッション）", "post", "/chat", 200, True, ["messages"],
                     json={"session_id": msid, "message": "診察室へどうぞ"})
        t.check("  裏の記憶の更新が終わる", box.wait_background(30))
        st = yaml.safe_load((box.sessions / msid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
        t.check("  進行状態は after / ready、進み具合は「その場の参加者 ＋ パーティー ＋ あらすじ ＋ 全員分」", (st.get("complete_stage"), st.get("status")) == ("after", "ready")
                and st.get("progress_done") == st.get("progress_total") == 3 + len(mem_files), st)

        # パーティー一覧の更新（→ docs/spec/chat-flow.md「発言1回分の流れ」7）
        parties_now = ((yaml.safe_load((box.sessions / msid / "world_memory.yaml").read_text(encoding="utf-8")) or {})
                       .get("現在の状態") or {}).get("パーティー一覧")
        t.check("パーティー: 発言のあと、パーティー一覧が更新される（プレイヤー・いない人・1人だけの組は外れる）",
                parties_now == [{"名前": "付き添い", "メンバー一覧": [{"キャラクターID": main_ids[0], "名前": next(
                    (x.get("表示名") for x in cast_people if x["参照ID"] == main_ids[0]), main_ids[0])},
                    {"キャラクターID": "guest_1", "名前": "田中"}]}], parties_now)
        t.check("  更新のプロンプトに、今回の会話と今のパーティーが入り、プレイヤーは登場人物に入らない",
                bool(party_prompts) and "診察室へどうぞ" in party_prompts[0] and "{current_parties}" not in party_prompts[0]
                and f"{pid}（" not in party_prompts[0].split("今のパーティー一覧")[0], party_prompts[:1])

        # 会話のあらすじ（→ docs/spec/chat-flow.md「発言1回分の流れ」8）
        summary = yaml.safe_load((box.sessions / msid / "summary.yaml").read_text(encoding="utf-8")) if (box.sessions / msid / "summary.yaml").exists() else {}
        t.check("あらすじ: 発言のあと、summary.yaml に箇条書きで保存される",
                (summary or {}).get("あらすじ") == ["結と圭太は診察室に通された。", "究也は来週の検査を約束した。"], summary)
        t.check("  更新のプロンプトに、今回の会話が入り、初回は「まだ無い」", bool(summary_prompts) and "診察室へどうぞ" in summary_prompts[0]
                and "（まだ無い）" in summary_prompts[0] and "{current_summary}" not in summary_prompts[0], summary_prompts[:1])

        # その場の参加者（→ docs/spec/chat-flow.md「発言1回分の流れ」7）
        wm = yaml.safe_load((box.sessions / msid / "world_memory.yaml").read_text(encoding="utf-8")) or {}
        now_ids = [x.get("キャラクターID") for x in (wm.get("現在の状態") or {}).get("参加者") or []]
        t.check("その場の参加者: 発言のあと、来た人・出て行った人に合わせて更新される（プレイヤーも先頭に入る）",
                now_ids == [pid, main_ids[0], "guest_1"], now_ids)
        session_world = yaml.safe_load(next((box.sessions / msid).glob("*_world.yaml")).read_text(encoding="utf-8")) or {}
        guest = next((x for x in session_world["登場人物"]["世界の登場人物"] if x.get("参照ID") == "guest_1"), {})
        t.check("  新しく現れた人は、セッションの登場人物に guest_1（inline・sub、職業に立場）で足される",
                (guest.get("参照種別"), guest.get("表示名"), guest.get("役割"), guest.get("職業")) == ("inline", "田中", "sub", "プレイヤーの友人"), guest)
        t.check("  その人の設定YAMLができる", (box.sessions / msid / "character" / "guest_1_setting.yaml").exists())
        t.check("  世界の参加者にも入る", any(x.get("キャラクターID") == "guest_1" for x in (wm.get("世界の状態") or {}).get("参加者") or []))
        t.check("  Web側の世界設定（元のファイル）は変えない",
                "guest_1" not in (box.web / "worlds" / "settings" / f"{world_id}_world.yaml").read_text(encoding="utf-8"))
        t.check("  更新のプロンプトに、世界の登場人物・今の参加者・今回の会話が入る",
                bool(present_prompts) and "診察室へどうぞ" in present_prompts[0] and "{current_present}" not in present_prompts[0])

        judge_prompts = []

        def judge_watch(prompt):
            if "誰に向けた物かを判別" in prompt:
                judge_prompts.append(prompt)
            return update_llm(prompt)

        box.client(llm=judge_watch).post("/chat", json={"session_id": msid, "message": "田中くん、来てたのか"})
        box.wait_background(30)
        jp = judge_prompts[0] if judge_prompts else ""
        t.check("  次の発言の候補は、その場にいる人だけ（田中は入り、出て行った人は入らない）",
                "guest_1（田中・プレイヤーの友人）" in jp and all(f"{o}（" not in jp for o in other_ids), jp[-400:])

        # 返事の前: 世界設定にいない人に声をかけたら、その発言で登場人物に足され、返事をする
        newcomer_answer["yaml"] = "呼ばれた人:\n  - キャラクターID: null\n    名前: 鈴木\n    役割: 看護師\n"
        judge_prompts.clear()
        reply_prompts = []
        suzuki_attention = []

        def call_suzuki(prompt):
            if "「意識を向けている相手」を特定する担当" in prompt:
                suzuki_attention.append(prompt)
                return "相手: guest_1"
            if "誰に向けた物かを判別" in prompt:
                judge_prompts.append(prompt)
                return "target_speakers: guest_2"
            if "あなたは 鈴木 として" in prompt:
                reply_prompts.append(prompt)
                return "（カルテを差し出して）\nはい、先生。こちらです"
            return update_llm(prompt)

        body = t.api(box.client(llm=call_suzuki), "chat（世界設定にいない人に声をかける）", "post", "/chat", 200, True, ["messages"],
                     json={"session_id": msid, "message": "鈴木さん、カルテください"})
        box.wait_background(30)
        first = (body.get("messages") or [{}])[0]
        t.check("  声をかけたその発言で、鈴木（guest_2）が返事をする",
                (first.get("icon_data", {}).get("character_id"), first.get("icon_data", {}).get("character_name")) == ("guest_2", "鈴木"), first)
        t.check("  メイン以外（鈴木）の返事は1行だけで、意識の確認も掛け合いもしない",
                len(body.get("messages") or []) == 1 and not suzuki_attention, [len(body.get("messages") or []), len(suzuki_attention)])
        t.check("  判定の候補に、足された鈴木が入っている", bool(judge_prompts) and "guest_2（鈴木・看護師）" in judge_prompts[0], judge_prompts[:1])
        t.check("  返事のプロンプトに、これまでのあらすじが入る",
                bool(reply_prompts) and "#これまでのあらすじ" in reply_prompts[0] and "究也は来週の検査を約束した。" in reply_prompts[0], reply_prompts[:1])
        before_now = present_prompts[-1].split("今のその場の参加者:")[1].split("今回の会話:")[0] if present_prompts else ""
        t.check("  鈴木は返事の前に、その場の参加者にも足されている（発言のあとの更新に渡す一覧に入る）", "guest_2" in before_now, before_now)
        newcomer_answer["yaml"] = "呼ばれた人: null"
        new_mem = yaml.safe_load(mem_path.read_text(encoding="utf-8")) or {}
        t.check("  記憶が今回の会話で更新される", (new_mem.get("現在の状態") or {}).get("場所") == "診察室", new_mem)
        old_rel = (old_mem.get("現在の状態") or {}).get("関係性") or []
        new_rel = (new_mem.get("現在の状態") or {}).get("関係性") or []
        t.check("  関係性: 前からいる人は、モデルが書き落としても残る", new_rel[:len(old_rel)] == old_rel, new_rel)
        t.check("  関係性: 新しく会った人（究也）が足される", any(isinstance(r, dict) and r.get("キャラクターID") == "kyuya" for r in new_rel), new_rel)
        t.check("  意識が更新される", (new_mem.get("現在の状態") or {}).get("意識") == ["究也"], new_mem)
        t.check("  更新のプロンプトに、今の記憶と今回の会話が入る",
                bool(update_prompts) and "診察室へどうぞ" in update_prompts[0] and "よろしくお願いします" in update_prompts[0]
                and "{current_memory}" not in update_prompts[0], update_prompts[:1])
        # 記憶の更新に渡す登場人物は、その場にいる人（プレイヤー・メイン・新しく来た田中）。出て行った人は入らない
        jobs = [x.get("職業") for x in world["登場人物"]["世界の登場人物"] if x.get("参照種別") in ("player", "character") and x.get("職業")] + ["プレイヤーの友人"]
        gone_jobs = [x.get("職業") for x in world["登場人物"]["世界の登場人物"] if x.get("参照種別") not in (None, "null", "player", "character") and x.get("職業")]
        t.check("  更新のプロンプトに、その場の登場人物が職業付きで入る（会話の「先生」と結び付けるため）",
                bool(update_prompts) and all(j in update_prompts[0] for j in jobs) and not any(j in update_prompts[0].split("今の記憶:")[0] for j in gone_jobs)
                and "{participants}" not in update_prompts[0], (jobs, gone_jobs))

        # 返事を記憶として読めなければ、error になり、記憶は前のまま
        update_calls = []

        def flaky_update(prompt):
            if "キャラクターの状態と記憶を更新するAI" in prompt:
                update_calls.append(1)
                if len(update_calls) == 1:
                    return "壊れた返事"            # 1回目だけ壊れている
            return update_llm(prompt)

        flaky = box.client(llm=flaky_update)
        flaky.post("/chat", json={"session_id": msid, "message": "聞き直しの確認"})
        box.wait_background(30)
        st = yaml.safe_load((box.sessions / msid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
        t.check("記憶の更新: 1回目が読めなくても、1回だけ聞き直して読めれば ready", (st.get("status"), len(update_calls)) == ("ready", 2), (st, len(update_calls)))

        broken_update = box.client(llm=lambda prompt: "壊れた返事" if "キャラクターの状態と記憶を更新するAI" in prompt else update_llm(prompt))
        before_text = mem_path.read_text(encoding="utf-8")
        broken_update.post("/chat", json={"session_id": msid, "message": "もう一度"})
        box.wait_background(30)
        st = yaml.safe_load((box.sessions / msid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
        t.check("記憶の更新に失敗: after / error、失敗した場所は character", (st.get("complete_stage"), st.get("status"), st.get("error_stage")) == ("after", "error", "character"), st)
        t.check("  記憶は前のまま", mem_path.read_text(encoding="utf-8") == before_text)
        body = t.api(broken_update, "  session_status で失敗が見える", "post", "/session_status", 200, True, ["status", "error_message"],
                     json={"session_id": msid})
    else:
        t.check("記憶のあるセッションが作れている", False, "初期記憶の生成で記憶ができていない")
    # 問い合わせの記録: logs/{セッションID}/{通し番号}_{時分秒}_{段階}.txt に、設定・送った内容・返事を1つのファイルで残す
    log_dir = box.server / "logs" / msid
    files = sorted(log_dir.glob("*.txt")) if log_dir.exists() else []
    names = [x.name for x in files]
    t.check("記録はセッションのフォルダに入る（logs/{セッションID}/）", bool(files), str(box.server / "logs"))
    t.check("  名前は「通し番号_時分秒_段階」で、通し番号は 0001 から順に並ぶ",
            bool(names) and [n[:4] for n in names] == [f"{i:04d}" for i in range(1, len(names) + 1)], names[:5])
    t.check("  段階の名前が入る（世界の記憶、要約、服装、所持金 など）",
            all(any(step in n for n in names) for step in ("世界の記憶", "要約_", "服装", "所持金")), names)
    body = files[0].read_text(encoding="utf-8") if files else ""
    t.check("  1つのファイルに、生成の設定・送った内容・返事が順に入る",
            body.index("===== 生成の設定 =====") < body.index("===== 送った内容 =====") < body.index("===== 返事 =====")
            if all(k in body for k in ("===== 生成の設定 =====", "===== 送った内容 =====", "===== 返事 =====")) else False, body[:200])
    t.check("  送った内容は、改行が \\n の文字ではなく、本当の改行で書かれる", "<|im_start|>system\n" in body and "\\n" not in body.split("===== 返事 =====")[0][:300], body[:120])

    scripted.post("/delete_session", json={"session_ids": [msid]})

    # キャラクターの記憶の段階（服装など）は、YAMLとして読めなければ1回だけ聞き直す
    def clothing_broken(times):
        count = []

        def llm(prompt):
            if "「現在の服装」を特定" in prompt:
                count.append(1)
                if len(count) <= times:
                    return "服装は、たぶんブレザーです"   # YAML の形でない返事
            return sandbox.scripted_llm(prompt)
        return llm, count

    for times, expect in ((1, "ready"), (2, "error")):
        llm, count = clothing_broken(times)
        c2 = box.client(llm=llm)
        rsid = (c2.post("/chat_startup", json={"world_id": world_id, "base_chat_path": web}).get_json() or {}).get("session_id", "")
        c2.post("/new_chat", json={"session_id": rsid})
        box.wait_background(60)
        st = yaml.safe_load((box.sessions / rsid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
        label = "1回目だけ壊れている → 聞き直して ready" if times == 1 else "2回とも壊れている → character で error"
        t.check(f"服装の段階: {label}", st.get("status") == expect and len(count) == 2
                and (expect == "ready" or st.get("error_stage") == "character"), (st.get("status"), st.get("error_stage"), len(count)))
        c2.post("/delete_session", json={"session_ids": [rsid]})

    # 世界の記憶で失敗したら、そこで止まり、失敗した場所(world)が残る
    broken = box.client(llm=lambda prompt: "壊れた返事" if "状態と記憶を構造化" in prompt else sandbox.scripted_llm(prompt))
    fsid = (broken.post("/chat_startup", json={"world_id": world_id, "base_chat_path": web}).get_json() or {}).get("session_id", "")
    before = len(box.llm_requests)
    broken.post("/new_chat", json={"session_id": fsid})
    box.wait_background(60)
    status = yaml.safe_load((box.sessions / fsid / "prepare_status.yaml").read_text(encoding="utf-8")) or {}
    t.check("世界の記憶で失敗: 状態は error、失敗した場所は world", (status.get("status"), status.get("error_stage")) == ("error", "world"), status)
    body = t.api(broken, "session_status（失敗）", "post", "/session_status", 200, True,
                 ["status", "error_stage", "error_message"], json={"session_id": fsid})
    t.check("  画面に出す失敗の情報が返る", (body.get("status"), body.get("error_stage")) == ("error", "world")
            and bool(body.get("error_message")), body)
    t.check("世界の記憶で失敗: キャラクターの記憶には進まない",
            not any("情報抽出担当" in q.get("prompt", "") for q in box.llm_requests[before:]))
    broken.post("/delete_session", json={"session_ids": [fsid]})
    client = box.client()                                # 以降は、モデルに接続できない扱いに戻す

    # ---------------------------------------------------------------- セッションに退避した画像
    print("\n# セッションに退避した画像")
    load_image("アイコン = 新規チャット時点の画像", f"/session_image/{sid}/icon/{cid}", 200, icon_png)
    load_image("立ち絵 = 新規チャット時点の画像", f"/session_image/{sid}/standing/{cid}", 200, standing_png)
    client.post("/settings/save_image", content_type="multipart/form-data", data={
        "base_chat_path": web, "owner_type": "character", "owner_id": cid, "image_type": "icon",
        "file": (io.BytesIO(standing_png), "new.png")})
    load_image("キャラクターの画像を変えても、進行中のセッションは元のまま", f"/session_image/{sid}/icon/{cid}", 200, icon_png)
    sid2 = (client.post("/chat_startup", json={"world_id": world_id, "base_chat_path": web}).get_json() or {}).get("session_id", "")
    load_image("新しいセッションには変更後の画像", f"/session_image/{sid2}/icon/{cid}", 200, standing_png)
    load_image("存在しないキャラクター → 404", f"/session_image/{sid}/icon/nobody", 404)
    load_image("存在しないセッション → 404", f"/session_image/no-such-session/icon/{cid}", 404)
    load_image("image_type 不正 → 400", f"/session_image/{sid}/thumb/{cid}", 400)
    load_image("キャラクターID 不正 → 400", f"/session_image/{sid}/icon/a.b", 400)
    load_image("セッションID 不正 → 400", f"/session_image/a.b/icon/{cid}", 400)

    # ---------------------------------------------------------------- 後片付け系
    print("\n# 削除")
    had_logs = (box.server / "logs" / sid).is_dir()
    body = t.api(client, "delete_session", "post", "/delete_session", 200, True,
                 ["deleted_session_ids", "failed_session_ids"], json={"session_ids": [sid, sid2]})
    t.check("  2件とも削除された", sorted(body.get("deleted_session_ids", [])) == sorted([sid, sid2]))
    t.check("  そのセッションの記録（logs/{セッションID}/）も消える", had_logs and not (box.server / "logs" / sid).exists(), had_logs)
    body = t.api(client, "一覧（削除後）", "post", "/load_session_list", 200, True, ["sessions"], json={"world_id": world_id})
    t.check("  一覧が空に戻った", body.get("sessions") == [])

    # ---------------------------------------------------------------- 世界・キャラクター・プレイヤーの削除
    print("\n# 世界・キャラクター・プレイヤーの削除")

    def delete(name, status, **body):
        return t.api(client, name, "post", "/settings/delete_setting", status, status == 200,
                     json=dict(base_chat_path=web, **body))

    body = delete("世界で使われているキャラクター → 409", 409, kind="character", id=cid)
    t.check("  使っている世界の名前が message に出る", world_name in (body.get("message") or ""), body.get("message"))
    t.check("  使っている世界の一覧が返る", any(w.get("id") == world_id for w in body.get("worlds", [])), body.get("worlds"))
    t.check("  ファイルは残っている", (box.web / "characters" / "settings" / f"{cid}_setting.yaml").exists())
    delete("世界で使われているプレイヤー → 409", 409, kind="player", id=pid)
    t.check("  ファイルは残っている", (box.web / "players" / "settings" / f"{pid}_setting.yaml").exists())

    client.post("/settings/save_character_setting", json={
        "base_chat_path": web, "character_id": "zz_c", "character_name": "消す人", "content": "名前:\n  表示名: 消す人\n"})
    delete("使われていないキャラクター", 200, kind="character", id="zz_c")
    t.check("  設定と画像のフォルダが消える", not any((box.web / "characters" / d).exists() for d in
            ("settings/zz_c_setting.yaml", "icon/zz_c", "standing/zz_c")))
    t.check("  他のキャラクターの画像は残る", (box.web / "characters" / "icon" / cid / f"{cid}.png").exists())

    # 世界を消しても、その世界のセッションは残る
    dsid = (client.post("/chat_startup", json={"world_id": "zz_verify", "base_chat_path": web}).get_json() or {}).get("session_id", "")
    delete("世界", 200, kind="world", id="zz_verify")
    t.check("  世界設定のファイルが消える", not (box.web / "worlds" / "settings" / "zz_verify_world.yaml").exists())
    t.api(client, "  消した世界のセッションは開ける", "post", "/selected_session", 200, True, ["message_list"],
          json={"session_id": dsid})
    client.post("/delete_session", json={"session_ids": [dsid]})

    delete("無いID → 404", 404, kind="world", id="no_such_world")
    delete("kind 不正 → 400", 400, kind="session", id="zz_c")
    delete("ID に ../ を含む → 400", 400, kind="character", id="../x")
    t.check("  サンドボックスの外が消えていない", (box.web / "characters" / "settings").exists())

    # ---------------------------------------------------------------- 形の統一
    print("\n# レスポンスの形")
    samples = {
        "/load_session_list": client.post("/load_session_list", json={"world_id": world_id}).get_json(),
        "/world_start (失敗)": client.post("/world_start", json={}).get_json(),
        "/chat (失敗)": client.post("/chat", json={"session_id": "x", "message": "x"}).get_json(),
    }
    for name, body in samples.items():
        old = [k for k in OLD_KEYS if k in (body or {})]
        t.check(f"{name} に旧形式のキーが無い", not old, f"残っているキー: {old}")

    return t.finish()


if __name__ == "__main__":
    sys.exit(main())
