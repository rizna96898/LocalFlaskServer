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

        result = self.model_handling_service.send_message(parameters)

        log.info("パラメーターエラーが無い事", result)

        responder = self._pick_target(result, candidates) or session_cast.first_main(cast)
        log.info("返事をする人", responder.get("id"))
        return result, responder

    # 判定の答え（target_speakers: ID）から、候補の人物を探す。見つからなければ None
    @staticmethod
    def _pick_target(result, candidates):
        try:
            data = yaml.safe_load(string_utils.strip_code_block(result or "")) or {}
        except Exception:
            return None
        if not isinstance(data, dict):
            return None

        target = data.get("target_speakers")
        if isinstance(target, list):
            target = target[0] if target else None
        if not target:
            return None

        target = str(target).strip()
        for person in candidates:
            if target in (person.get("id"), person.get("name")):
                return person
        return None