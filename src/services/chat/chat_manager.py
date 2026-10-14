from chat_builders.prompt_builder import ChatPromptBuilder
from services.llm.llm_service import ModelHandlingService
from services.llm import generation_params
from config import config
from constant import PromptsMain
from helpers import file_utils
from logger import log

class ChatManager:
    def __init__(self):
        self.prompt_builder = ChatPromptBuilder()
        self.model_handling_service = ModelHandlingService("local")
        # log.info("[MemoryManager] Initialized")

    def main_chat(self, body, session_id, message) -> str:

        prompt_messages = self.prompt_builder.create_discrimination_prompt(session_id, message)
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
        return result