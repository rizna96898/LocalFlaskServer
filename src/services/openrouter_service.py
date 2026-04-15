# src/services/openrouter_service.py
"""
OpenRouterとの通信を専門に扱うサービスクラス
設定はすべて config（system_settings.yaml）から取得
"""

import requests
from typing import List, Dict, Any, Optional

from config import config


class OpenRouterService:
    def __init__(self):
        self.base_url = "https://openrouter.ai/api/v1"
        
        # configからすべての設定を取得
        self.api_key = config.OPENROUTER_API_KEY
        self.default_model = config.DEFAULT_MODEL
        self.temperature = config.TEMPERATURE
        self.max_tokens = config.MAX_TOKENS

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": config.OPENROUTER_SITE_URL,
            "X-Title": config.OPENROUTER_SITE_NAME,
            "Content-Type": "application/json"
        }

        # APIキーの確認
        if not self.api_key or self.api_key == "dummy":
            print("[WARN] OpenRouter APIキーが設定されていません。system_settings.yamlを確認してください。")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        OpenRouterにメッセージを送信し、応答のcontent部分を返す
        """
        if not self.api_key or self.api_key == "dummy":
            raise ValueError("OpenRouter APIキーが設定されていません。system_settings.yamlに正しいキーを設定してください。")

        # パラメータの優先順位: 引数 > config
        target_model = model or self.default_model
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # system_promptがある場合は先頭に追加
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})

        payload_messages.extend(messages)

        print("送信内容：", payload_messages)
        
        payload = {
            "model": target_model,
            "messages": payload_messages,
            "temperature": temp,
            "max_tokens": tokens,
            **kwargs
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=90
            )
            
            response.raise_for_status()

            data = response.json()
            #print("[OPENROUTER RAW JSON]", data)

            if "choices" not in data:
                raise Exception(f"OpenRouter response missing 'choices': {data}")
            
            content = data["choices"][0]["message"]["content"]

            # 簡単なログ出力
            #usage = data.get("usage", {})
            #print(f"[OpenRouter] Model: {target_model} | Prompt: {usage.get('prompt_tokens')} | Completion: {usage.get('completion_tokens')}")

            return content.strip()

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] OpenRouter API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status Code: {e.response.status_code}")
                try:
                    print(f"Response: {e.response.json()}")
                except:
                    print(f"Response text: {e.response.text}")
            raise

        except (KeyError, IndexError, TypeError) as e:
            print(f"[ERROR] Failed to parse OpenRouter response: {e}")
            raise Exception(f"OpenRouter response parsing error: {e}")

    def send_with_system(self, messages: List[Dict], system_prompt: str, **kwargs) -> str:
        """system_promptを明確に指定したいとき用の便利メソッド"""
        return self.send_message(messages, system_prompt=system_prompt, **kwargs)