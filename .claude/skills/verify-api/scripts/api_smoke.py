"""全APIを一通り呼ぶスモークテスト。本物のデータには触れない。

    py -3 .claude/skills/verify-api/scripts/api_smoke.py

確かめること:
- レスポンスの形（成功は ok: true、失敗は ok: false + message + HTTPステータス）
- 設定系（テンプレート、世界・キャラクターの保存と読み込み、画像）
- セッション系（一覧、作成、履歴、再送、削除）
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
    t.api(client, "load_model", "post", "/settings/load_model", 200, True, json={"base_path": str(box.server)})
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
    t.api(client, "selected_session", "post", "/selected_session", 200, True, ["session_id", "message_list"],
          json={"session_id": sid})

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

    t.api(client, "chat（モデルサーバー停止中）→ 500", "post", "/chat", 500, False,
          json={"session_id": sid, "message": "こんにちは"})
    body = t.api(client, "re_chat", "post", "/re_chat", 200, True, ["session_id", "line_id", "message", "icon_data"],
                 json={"session_id": sid, "message": "てすと"})
    # 開始メッセージ(1)、再送のプレイヤーの発言(2)、再送の返事(3)。/chat は失敗したので何も足さない
    t.check("  line_id は発言ごとの通し番号（再送の返事は 3）", body.get("line_id") == "3", body.get("line_id"))
    body = t.api(client, "履歴に追記されている", "post", "/selected_session", 200, True, ["message_list"],
                 json={"session_id": sid})
    t.check("  履歴の番号が 1, 2, 3", [m.get("line_id") for m in body.get("message_list", [])] == ["1", "2", "3"],
            [m.get("line_id") for m in body.get("message_list", [])])

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
    memories = sorted(p.name for p in (box.sessions / msid / "character").glob("*_memory.yaml"))
    t.check("キャラクターの記憶ができる", len(memories) >= 1, memories)
    sent = box.llm_requests[before:]
    stages = ["状態と記憶を構造化", "情報抽出担当", "「居場所」を特定", "分類機", "「現在の服装」を特定",
              "「現在の所持品」を特定", "「意識を向けている相手」を特定", "「所持金」を確定"]
    missing = [s for s in stages if not any(s in q.get("prompt", "") for q in sent)]
    t.check("全段階（世界 ＋ キャラクター7段階）のプロンプトが送られる", not missing, f"送られていない段階: {missing}")

    # 生成の設定は files/settings/generation.yaml から読む（→ docs/spec/prompts.md「生成の設定」）
    wanted = yaml.safe_load(box.generation_file.read_text(encoding="utf-8")) or {}
    expect = dict(wanted.get("default") or {}, **(wanted.get("memory") or {}))
    wrong = [q for q in sent if any(q.get(k) != v for k, v in expect.items())]
    t.check("送信した設定が generation.yaml の memory の値と一致", bool(expect) and not wrong,
            f"期待 {expect} / 違うもの {len(wrong)} 件")
    scripted.post("/delete_session", json={"session_ids": [msid]})

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
    body = t.api(client, "delete_session", "post", "/delete_session", 200, True,
                 ["deleted_session_ids", "failed_session_ids"], json={"session_ids": [sid, sid2]})
    t.check("  2件とも削除された", sorted(body.get("deleted_session_ids", [])) == sorted([sid, sid2]))
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
