# src/services/llm_service.py
"""
OpenRouterとの通信を専門に扱うサービスクラス
設定はすべて config（system_settings.yaml）から取得
"""

import requests
import time
import threading
from llama_cpp import Llama
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import config

class ModelHandlingService:
    def __init__(self, mode="openrouter"):
        mode = (mode or "openrouter").lower()

        if mode == "openrouter":
            if not config.OPENROUTER_USE_FLAG:
                raise RuntimeError("OpenRouterが無効なのにmodeがopenrouterになってる")
            self.impl = OpenRouterService(api_key=config.OPENROUTER_API_KEY)

        elif mode == "local":
            if not config.LOCALMODEL_USE_FLAG:
                raise RuntimeError("LocalModelが無効なのにmodeがlocalになってる")
            model_file_path = Path(config.LOCALMODEL_PATH)
            model_file_name = config.LOCALMODEL_NAME
            self.llm = Llama(
                model_path=str(model_file_path / model_file_name),
                n_ctx=3072,
                n_gpu_layers=-1,  # GPUに載せる。重ければ数値指定
                verbose=True,
            )
            self.impl = LocalModelService(llm=self.llm)

        else:
            raise ValueError(f"未知のmode: {mode}")
    
    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        # ここでだけ軽く補完
        if max_tokens is None:
            max_tokens = 512

        return self.impl.send_message(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    def _get_default_max_tokens(self, task_type):
        if task_type == "chat":
            return 400
        elif task_type == "memory":
            return 1500
        elif task_type == "judge":
            return 200
        return 800

class LocalModelService:
    _llm_lock = threading.Lock()
    def __init__(self, llm):
        self.llm = llm
        self.temperature = config.TEMPERATURE
        self.max_tokens = config.MAX_TOKENS

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
        LocalModelにメッセージを送信し、応答のcontent部分を返す
        """

        # パラメータの優先順位: 引数 > config
        model_name = config.LOCALMODEL_NAME
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # system_promptがある場合は先頭に追加
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})

        payload_messages.extend(messages)

        started_at = time.time()

        print(payload_messages)
        prompt = messages_to_prompt(payload_messages)
        
        print("=== LOCAL PROMPT TAIL ===")
        print(prompt[-1000:])
        print("=========================")

        try:
            print(f"[LOCALMODEL] send_message start: model={model_name}, started_at={started_at}")

            # print(f"[OPENROUTER] requests.post start: elapsed={time.time() - started_at:.2f}s")
            response = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.7,
                # stop=["user:", "system:"]
            )
            # print(f"[OPENROUTER] requests.post end: elapsed={time.time() - started_at:.2f}s")
            print(f"[LOCALMODEL] send_message end: model={model_name}, ended_at={time.time()}")

            choice = response["choices"][0]

            content = choice.get("text")

            # Noneチェック
            if content is None:
                raise ValueError(
                    f"[LOCALMODEL] content is None | response={response}"
                )

            # 空文字チェック（今回まさにこれで落ちてた）
            content = content.strip()
            if content == "":
                print("[LOCALMODEL WARNING] empty response")
                print("finish_reason:", choice.get("finish_reason"))
                print("prompt_tokens:", response.get("usage", {}).get("prompt_tokens"))
                raise ValueError(
                    f"[LOCALMODEL] empty content | finish_reason={choice.get('finish_reason')} | response={response}"
                )

            result = content.strip()
            # print(f"[OPENROUTER] send_message success: elapsed={time.time() - started_at:.2f}s, length={len(result)}")

            return result

        except requests.exceptions.Timeout as e:
            print(f"[LOCALMODEL TIMEOUT] elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] LOCALMODEL request failed: elapsed={time.time() - started_at:.2f}s: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Status Code: {e.response.status_code}")
                try:
                    print(f"Response: {e.response.json()}")
                except Exception:
                    print(f"Response text: {e.response.text}")
            raise

        except (KeyError, IndexError, TypeError) as e:
            print(f"[ERROR] Failed to parse LOCALMODEL response: elapsed={time.time() - started_at:.2f}s: {e}")
            raise Exception(f"LOCALMODEL response parsing error: {e}")

        except Exception as e:
            print(f"[ERROR] Unexpected error in send_message: elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        finally:
            print(f"[LOCALMODEL] send_message end")


    def send_with_system(self, messages: List[Dict], system_prompt: str, **kwargs) -> str:
        """system_promptを明確に指定したいとき用の便利メソッド"""
        return self.send_message(messages, system_prompt=system_prompt, **kwargs)

class OpenRouterService:
    def __init__(self, api_key):
        self.base_url = "https://openrouter.ai/api/v1"
        self.api_key = api_key
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

# OpenRouterとLocalModelで渡す状態を変えるのが辛いので一旦ここで吸収
def messages_to_prompt(payload_messages):
    lines = []

    for m in payload_messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        if role == "system":
            lines.append(f"### Instruction:\n{content}")
        elif role == "user":
            lines.append(f"### Instruction:\n{content}")
        elif role == "assistant":
            lines.append(f"### Response:\n{content}")

    lines.append("### Response:")

    return "\n".join(lines)