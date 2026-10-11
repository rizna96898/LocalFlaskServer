#use_memory_constant.py
from typing import List, Dict, Any

# それぞれで必要なパラメーター等半動的情報を纏める
def get_chat_send_parameters(prompt_messages: List[Dict]):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = prompt_messages
    parameters["system_prompt"]   = ""
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = {"248068": -5}
    return parameters

