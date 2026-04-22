# src/services/openrouter_service.py
"""
OpenRouterとの通信を専門に扱うサービスクラス
設定はすべて config（system_settings.yaml）から取得
"""

import requests
import time
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

        payload = {
            "model": target_model,
            "messages": payload_messages,
            "temperature": temp,
            "max_tokens": tokens,
            **kwargs
        }

        started_at = time.time()

        try:
            print(f"[OPENROUTER] send_message start: model={target_model}, started_at={started_at}")

            # print(f"[OPENROUTER] requests.post start: elapsed={time.time() - started_at:.2f}s")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=(10, 90)   # connect timeout, read timeout
            )
            # print(f"[OPENROUTER] requests.post end: elapsed={time.time() - started_at:.2f}s")
            print(f"[OPENROUTER] send_message end: model={target_model}, ended_at={time.time()}")

            # print(f"[OPENROUTER] raise_for_status start: elapsed={time.time() - started_at:.2f}s, status={response.status_code}")
            response.raise_for_status()
            # print(f"[OPENROUTER] raise_for_status end: elapsed={time.time() - started_at:.2f}s")

            # print(f"[OPENROUTER] response.json start: elapsed={time.time() - started_at:.2f}s")
            data = response.json()
            # print(f"[OPENROUTER] response.json end: elapsed={time.time() - started_at:.2f}s")

            if "choices" not in data:
                raise Exception(f"OpenRouter response missing 'choices': {data}")
            
            # print(f"[OPENROUTER] content extract start: elapsed={time.time() - started_at:.2f}s")
            
            choices = data.get("choices") or []
            choice0 = choices[0] if choices else {}
            message0 = choice0.get("message", {}) if isinstance(choice0, dict) else {}
            content = message0.get("content") if isinstance(message0, dict) else None

            if content is None:
                raise ValueError(
                    "[OpenRouter] content is None | "
                    f"model={model} | "
                    f"finish_reason={choice0.get('finish_reason') if isinstance(choice0, dict) else None} | "
                    f"message_keys={list(message0.keys()) if isinstance(message0, dict) else None} | "
                    f"choice_keys={list(choice0.keys()) if isinstance(choice0, dict) else None} | "
                    f"response={data!r}"
                )

            # print(f"[OPENROUTER] content extract end: elapsed={time.time() - started_at:.2f}s")

            result = content.strip()
            # print(f"[OPENROUTER] send_message success: elapsed={time.time() - started_at:.2f}s, length={len(result)}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[OPENROUTER TIMEOUT] elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] OpenRouter API request failed: elapsed={time.time() - started_at:.2f}s: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Status Code: {e.response.status_code}")
                try:
                    print(f"Response: {e.response.json()}")
                except Exception:
                    print(f"Response text: {e.response.text}")
            raise

        except (KeyError, IndexError, TypeError) as e:
            print(f"[ERROR] Failed to parse OpenRouter response: elapsed={time.time() - started_at:.2f}s: {e}")
            raise Exception(f"OpenRouter response parsing error: {e}")

        except Exception as e:
            print(f"[ERROR] Unexpected error in send_message: elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        finally:
            print(f"[OPENROUTER] send_message end")


    def send_with_system(self, messages: List[Dict], system_prompt: str, **kwargs) -> str:
        """system_promptを明確に指定したいとき用の便利メソッド"""
        return self.send_message(messages, system_prompt=system_prompt, **kwargs)