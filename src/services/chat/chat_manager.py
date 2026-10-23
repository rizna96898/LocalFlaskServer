from chat_builders.prompt_builder import ChatPromptBuilder
from services.llm.llm_service import ModelHandlingService
from services.llm import generation_params
from config import config
from constant import PromptsMain
from helpers import file_utils
from helpers import session_cast
from helpers import string_utils
from logger import log
import re
import yaml

# プロンプトに入れる「これまでの会話」の行数（会話ログの最後から）
RECENT_LOG_LINES = 10


# 設定YAMLから、空の項目を取り除く。null、空文字、0、「0cm」のような0だけの値、中身が空になった配列や辞書は消す
# （テンプレートから作ったサブの設定は、名前以外がほぼこれで、送っても雑音にしかならない）
def _drop_empty(data):
    if isinstance(data, dict):
        cleaned = {key: _drop_empty(value) for key, value in data.items()}
        return {key: value for key, value in cleaned.items() if value is not None} or None
    if isinstance(data, list):
        cleaned = [_drop_empty(value) for value in data]
        cleaned = [value for value in cleaned if value is not None]
        return cleaned or None
    if data is None or data is False:
        return None
    if isinstance(data, (int, float)):
        return data or None
    text = str(data).strip()
    if text in ("", "null", "None") or re.fullmatch(r"0+\D{0,3}", text):
        return None
    return data


class ChatManager:
    def __init__(self):
        self.prompt_builder = ChatPromptBuilder()
        self.model_handling_service = ModelHandlingService("local")
        # log.info("[MemoryManager] Initialized")

    # 返事をする人を決める。プレイヤーの発言が誰に向けたものかを判定し、言われた相手にする。
    # 判定できなければ、最初のメイン。戻り値は (判定の答えそのもの, 返事をする人)
    def main_chat(self, body, session_id, message, cast, previous_message="") -> tuple:

        candidates = cast.get("characters") or []
        prompt_messages = self.prompt_builder.create_discrimination_prompt(candidates, previous_message, message)
        log.info("プロンプトエラーが無い事", prompt_messages)

        # 誰に向けた発言かの判定なので、用途は judge（短い答えで足りる）
        parameters = generation_params.build_send_parameters(
            "judge",
            messages=prompt_messages,
            prompt_data=file_utils.load_yaml_file(config.MAIN / PromptsMain.CHARACTER_IDENTIFICATION),
        )

        log.info("パラメーターエラーが無い事", parameters)

        log.set_step("判定")
        result = self.model_handling_service.send_message(parameters)

        log.info("パラメーターエラーが無い事", result)

        responder = self._pick_target(result, candidates) or session_cast.first_main(cast)
        log.info("返事をする人", responder.get("id"))
        return result, responder

    # 返事を作る。speaker が、partner の発言（partner_message）に返事をする
    # history: これまでの会話ログ（partner_message はまだ入っていないもの）
    def reply(self, session_id, speaker, partner, partner_message, history) -> str:
        context = self._context(session_id, speaker, history)
        context["participants"] = self._participants(session_id, speaker)
        prompt_messages = self.prompt_builder.create_reply_prompt({
            **context,
            "partner_name": partner["name"],
            "partner_message": partner_message,
        })
        return self._send("chat", prompt_messages, PromptsMain.CHAT, f"返事_{speaker['id']}")

    # 返事のあと、speaker の意識が今だれに向いているか。登場人物（プレイヤーを含む）から1人、見つからなければ None
    # history: 今の返事まで入った会話ログ
    def attention(self, session_id, speaker, cast, history):
        people = [cast["player"]] + list(cast.get("characters") or [])
        # 返事の相手と、意識の向きは同じとは限らない。直前までの記憶（意識・心情・行動）も渡して判断させる
        prompt_messages = self.prompt_builder.create_attention_prompt({
            "character_name": speaker["name"],
            "participants": "\n".join(session_cast.label(p) for p in people if p["id"] != speaker["id"]),
            "recent_log": self._recent_log(history),
            "character_memory": self._context(session_id, speaker, history)["character_memory"],
            "parties": session_cast.parties_text(session_id),
        })
        result = self._send("judge", prompt_messages, PromptsMain.ATTENTION, f"意識_{speaker['id']}")

        try:
            data = yaml.safe_load(string_utils.strip_code_block(result or "")) or {}
        except Exception:
            data = {}
        answer = data.get("相手") if isinstance(data, dict) else None
        target = self._find_person(answer, people)
        log.info("意識の向き", speaker["id"], "→", target["id"] if target else None)
        return target

    # 掛け合いの話しかけ。speaker が target に一言話しかける。
    # previous は speaker の直前の発言（同じ言葉を繰り返させないために渡す）
    def cross_talk(self, session_id, speaker, target, history, previous="") -> str:
        context = self._context(session_id, speaker, history)
        context["participants"] = self._participants(session_id, speaker)
        prompt_messages = self.prompt_builder.create_cross_talk_prompt({
            **context,
            "target_name": target["name"],
            "previous_line": previous or "（なし）",
        })
        return self._send("chat", prompt_messages, PromptsMain.CROSS_TALK, f"話しかけ_{speaker['id']}")

    # 返事の前に、speaker が mates（同じパーティーでその場にいる人）のだれかに相談するか。相談する相手、しなければ None
    # history: これまでの会話ログ（プレイヤーの発言はまだ入っていないもの）
    def consult_check(self, session_id, speaker, mates, player, player_message, history):
        prompt_messages = self.prompt_builder.create_consult_check_prompt({
            "character_name": speaker["name"],
            "mates": "\n".join(session_cast.label(p) for p in mates),
            "parties": session_cast.parties_text(session_id),
            "character_memory": self._context(session_id, speaker, history)["character_memory"],
            "recent_log": self._recent_log(history),
            "player_name": player["name"],
            "player_message": player_message,
        })
        result = self._send("judge", prompt_messages, PromptsMain.CONSULT_CHECK, f"相談の確認_{speaker['id']}")

        try:
            data = yaml.safe_load(string_utils.strip_code_block(result or "")) or {}
        except Exception:
            data = {}
        answer = data.get("相談") if isinstance(data, dict) else None
        mate = self._find_person(answer, mates)
        log.info("相談の相手", speaker["id"], "→", mate["id"] if mate else None)
        return mate

    # 相談の話しかけ。speaker が、プレイヤーの発言に答える前に mate へ相談する一言
    def consult(self, session_id, speaker, mate, player, player_message, history) -> str:
        context = self._context(session_id, speaker, history)
        context["participants"] = self._participants(session_id, speaker)
        prompt_messages = self.prompt_builder.create_consult_prompt({
            **context,
            "target_name": mate["name"],
            "player_name": player["name"],
            "player_message": player_message,
        })
        return self._send("chat", prompt_messages, PromptsMain.CONSULT, f"相談_{speaker['id']}")

    # プレイヤーの発言で、名前で呼ばれた人を、呼ばれた順に返す（返事をする人の候補）。
    # モデルには名前を書いてあるとおりに抜き出させるだけで、登場人物の誰に当たるかはここで照らし合わせる。
    # 1つの名前が何人にも当たる（白井 → 結と圭太）ときは、メインキャラクターを優先し、それでも決まらなければ使わない
    def called_responders(self, session_id, cast, message) -> list:
        prompt_messages = self.prompt_builder.create_called_names_prompt({
            "player_name": cast["player"]["name"],
            "player_message": message,
        })
        result = self._send("judge", prompt_messages, PromptsMain.CALLED_NAMES, "呼ばれた名前")

        try:
            data = yaml.safe_load(string_utils.strip_code_block(result or "")) or {}
        except Exception:
            data = {}
        names = data.get("呼ばれた名前") if isinstance(data, dict) else None
        if not isinstance(names, list):
            return []

        candidates = list(cast.get("characters") or [])
        responders = []
        for name in names:
            person = self._match_called_name(name, candidates)
            if person and person not in responders:
                responders.append(person)

        log.info("呼ばれた名前", names, "→", [p["id"] for p in responders])
        return responders

    # 呼ばれた名前（白井、結、白井結 など）が、候補のだれに当たるか。表示名・名字・下の名前・IDで比べる
    @staticmethod
    def _match_called_name(name, candidates):
        def norm(s):
            return "".join(str(s or "").split())

        called = norm(name)
        for honorific in ("さん", "くん", "君", "ちゃん", "様", "さま", "先生"):
            if called.endswith(honorific) and len(called) > len(honorific):
                called = called[: -len(honorific)]
        if not called:
            return None

        hits = []
        for person in candidates:
            parts = str(person.get("name") or "").replace("　", " ").split()
            if called in (person.get("id"), norm(person.get("name"))) or called in parts:
                hits.append(person)

        if len(hits) == 1:
            return hits[0]
        mains = [p for p in hits if p.get("kind") == "character"]
        return mains[0] if len(mains) == 1 else None

    # ---------------------------------------------------------------- 内部

    def _send(self, task_type, prompt_messages, prompt_file, step="問い合わせ") -> str:
        log.set_step(step)
        parameters = generation_params.build_send_parameters(
            task_type,
            messages=prompt_messages,
            prompt_data=file_utils.load_yaml_file(config.MAIN / prompt_file),
        )
        result = self.model_handling_service.send_message(parameters)
        return string_utils.strip_code_block(result or "").strip()

    # 返事を作るときの材料。キャラクター設定・今の記憶・これまでの会話
    def _context(self, session_id, person, history) -> dict:
        char_dir = config.SESSIONS_DIR / session_id / "character"

        setting = file_utils.load_yaml_file(char_dir / f"{person['id']}_setting.yaml")
        memory = file_utils.load_yaml_file(char_dir / f"{person['id']}_memory.yaml")

        # 記憶の無い人（サブなど）は、世界の記憶の参加者（関係性）を記憶の代わりにする
        if not memory:
            world_memory = file_utils.load_yaml_file(config.SESSIONS_DIR / session_id / "world_memory.yaml")
            memory = {
                "関係性": {
                    "その場の参加者": (world_memory.get("現在の状態") or {}).get("参加者"),
                    "世界の参加者": (world_memory.get("世界の状態") or {}).get("参加者"),
                }
            }

        # これまでのあらすじ（発言のあとに更新している。最後の10行より前の話の要点）
        summary = (file_utils.load_yaml_file(config.SESSIONS_DIR / session_id / "summary.yaml") or {}).get("あらすじ") or []

        # 話す人が誰か。「名前（職業）」。サブは設定がほぼ空なので、立場をはっきり書かないと、ほかの人の立場で話すことがある
        role = person.get("job") or ""
        character_self = f"{person['name']}（{role}）" if role else person["name"]

        return {
            "character_name": person["name"],
            "character_self": character_self,
            # 設定のうち、空の項目（null、0、テンプレートのまま）は送らない（サブの設定は、ほぼ全部が空）
            "character_info": self._dump(_drop_empty(setting)) or character_self,
            "character_memory": self._dump(memory),
            "recent_log": self._recent_log(history),
            "story_summary": "\n".join(f"- {line}" for line in summary) or "（まだ無い）",
        }

    # その場の登場人物（自分以外。その場にいる人だけ）。「ID（表示名・職業）」を1行ずつ
    @staticmethod
    def _participants(session_id, speaker) -> str:
        cast = session_cast.present_cast(session_id)
        people = [cast["player"]] + list(cast.get("characters") or [])
        return "\n".join(session_cast.label(p) for p in people if p["id"] != speaker["id"])

    @staticmethod
    def _dump(data) -> str:
        if not data:
            return ""
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()

    @staticmethod
    def _recent_log(history) -> str:
        lines = []
        for item in (history or [])[-RECENT_LOG_LINES:]:
            name = (item.get("icon_data") or {}).get("character_name") or item.get("speaker") or ""
            lines.append(f"{name}: {item.get('message', '')}")
        return "\n".join(lines)

    # 答え（ID か表示名）から人物を探す。表示名は空白（半角・全角）を無視して比べる
    @staticmethod
    def _find_person(answer, people):
        if isinstance(answer, list):
            answer = answer[0] if answer else None
        if not answer or str(answer).strip() in ("null", "None", "unknown"):
            return None

        def norm(s):
            return "".join(str(s).split()).replace("　", "")

        answer = str(answer).strip()
        for person in people:
            if answer == person.get("id") or norm(answer) == norm(person.get("name", "")):
                return person
        return None

    # 判定の答え（target_speakers: ID）から、候補の人物を探す。見つからなければ None
    @classmethod
    def _pick_target(cls, result, candidates):
        try:
            data = yaml.safe_load(string_utils.strip_code_block(result or "")) or {}
        except Exception:
            return None
        if not isinstance(data, dict):
            return None

        return cls._find_person(data.get("target_speakers"), candidates)
