from chat_builders.prompt_builder import ChatPromptBuilder
from services.llm.llm_service import ModelHandlingService
from chat_builders import use_chat_constant
from logger import log

class ChatManager:
    def __init__(self):
        self.prompt_builder = ChatPromptBuilder()
        self.model_handling_service = ModelHandlingService("local")
        # log.info("[MemoryManager] Initialized")

    def main_chat(self, body, session_id, message) -> str:

        prompt_messages = self.prompt_builder.create_discrimination_prompt(session_id, message)
        log.info("プロンプトエラーが無い事", prompt_messages)

        parameters = use_chat_constant.get_chat_send_parameters(prompt_messages)

        log.info("パラメーターエラーが無い事", parameters)

        result = self.model_handling_service.send_message(parameters)

        log.info("パラメーターエラーが無い事", result)
        return result