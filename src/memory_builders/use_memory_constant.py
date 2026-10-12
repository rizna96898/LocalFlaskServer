#use_memory_constant.py
from typing import List, Dict, Any
# それぞれで必要なパラメーター等半動的情報を纏める
def get_world_memory_send_parameters(prompt_messages: List[Dict]):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = prompt_messages
    parameters["system_prompt"]   = ""
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_summary_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_categorize_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_location_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_clothing_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_items_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_target_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

def get_character_middle_currency_send_parameters(system_prompt: str, prompt_messages: str):
    parameters = {}
    parameters["task_type"]       = "memory"
    parameters["prompt_messages"] = [
                        {
                            "role": "user",
                            "content": prompt_messages,
                        }
                    ]
    parameters["system_prompt"]   = system_prompt
    parameters["temperature"]     = 0.5
    parameters["top_p"]           = 0.9
    parameters["stop"]            = []
    parameters["top_k"]           = 0
    parameters["repeat_penalty"]  = 1.1
    parameters["logit_bias"]      = None
    return parameters

