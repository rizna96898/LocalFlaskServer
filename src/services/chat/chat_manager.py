from chat_builders.prompt_builder import ChatPromptBuilder
from services.llm.llm_service import ModelHandlingService
from services.llm import generation_params
from config import config
from constant import PromptsMain
from helpers import file_utils
from helpers import session_cast
from helpers import string_utils
from logger import log
import yaml

# プロンプトに入れる「これまでの会話」の行数（会話ログの最後から）
RECENT_LOG_LINES = 10


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

    # 掛け合いの話しかけ。speaker が target に一言話しかける
    def cross_talk(self, session_id, speaker, target, history) -> str:
        context = self._context(session_id, speaker, history)
        context["participants"] = self._participants(session_id, speaker)
        prompt_messages = self.prompt_builder.create_cross_talk_prompt({
            **context,
            "target_name": target["name"],
        })
        return self._send("chat", prompt_messages, PromptsMain.CROSS_TALK, f"話しかけ_{speaker['id']}")

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

        return {
            "character_name": person["name"],
            "character_info": self._dump(setting) or person["name"],
            "character_memory": self._dump(memory),
            "recent_log": self._recent_log(history),
        }

    # その場の登場人物（自分以外）。「ID（表示名・職業）」を1行ずつ
    @staticmethod
    def _participants(session_id, speaker) -> str:
        cast = session_cast.load_cast(session_id)
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
