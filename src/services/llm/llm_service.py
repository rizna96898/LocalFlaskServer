# src/services/llm_service.py
"""
OpenRouterとの通信を専門に扱うサービスクラス
設定はすべて config（system_settings.yaml）から取得
"""
import requests
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import config
from logger import log
from helpers import string_utils
from helpers import response_checker
from services.systems import system_settings_reload_service

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
            self.impl = LocalModelService()

        else:
            raise ValueError(f"未知のmode: {mode}")
    
    def send_message(self, send_data: Dict):
        max_tokens = self._get_default_max_tokens(send_data.get("task_type"))
        return self.impl.send_message(
            messages=send_data.get("prompt_messages"),
            system_prompt=send_data.get("system_prompt"),
            temperature=send_data.get("temperature"),
            top_p=send_data.get("top_p"),
            top_k = send_data.get("top_k"),
            repeat_penalty = send_data.get("repeat_penalty"),
            max_tokens = max_tokens,
            stop=send_data.get("stop"),
            logit_bias= send_data.get("logit_bias"),
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
    def __init__(self):
        self.server_url = config.LOCALMODEL_SERVER_URL
        self.temperature = config.TEMPERATURE
        self.max_tokens = config.MAX_TOKENS

    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        logit_bias: Optional[Dict[str, int]] = None,
        **kwargs
    ) -> str:
        """
        LocalModelにメッセージを送信し、応答のcontent部分を返す
        """
        log.info("[LOCALMODEL] send_message start")

        # パラメータの優先順位: 引数 > config
        model_name = config.LOCALMODEL_NAME

        # system_promptがある場合は先頭に追加
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})

        payload_messages.extend(messages)

        started_at = time.time()

        log.info(payload_messages)
        prompt = messages_to_prompt(payload_messages)

        log.info("=== LOCAL PROMPT TAIL ===")
        log.info("[LOCALMODEL] 送信予定文", prompt)
        log.info("=========================")
        
        try:
            log.info(f"[LOCALMODEL] send_message start: model={model_name}, started_at={started_at}")

            log.debug_dump_all(
                prompt,
                {
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "repeat_penalty": repeat_penalty,
                    "max_tokens": max_tokens,
                    "stop": stop,
                    "logit_bias": logit_bias,
                }
            )
            # log.info(f"[OPENROUTER] requests.post start: elapsed={time.time() - started_at:.2f}s")
            start = time.perf_counter()
            response = requests.post(
                self.server_url,
                json={
                    "prompt": prompt,
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "repeat_penalty": repeat_penalty,
                    "max_tokens": max_tokens,
                    "stop": stop,
                    "logit_bias": logit_bias,
                },
                timeout=(10, 600),
            )

            response.raise_for_status()
            response = response.json()
            elapsed = time.perf_counter() - start

            log.info("返信結果全部", response)
            log.info(f"[LOCALMODEL] send_message end: model={model_name}, ended_at={time.time()}")

            choice = response["choices"][0]
            content = choice.get("text")

            # Noneチェック
            if content is None:
                raise ValueError(
                    f"[LOCALMODEL] content is None | response={response}"
                )

            response_text = content.strip()
            usage = response.get("usage", {})

            log.performance(model_name,
            elapsed,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("total_tokens", 0),
            len(response_text),)

            # 空文字チェック（今回まさにこれで落ちてた）
            content = content.strip()
            if content == "":
                for retry in range(2):
                    response = requests.post(
                        self.server_url,
                        json={
                            "prompt": prompt,
                            "temperature": temperature,
                            "top_p": top_p,
                            "top_k": top_k,
                            "repeat_penalty": repeat_penalty,
                            "max_tokens": max_tokens,
                            "stop": stop,
                            "logit_bias": logit_bias,
                        },
                        timeout=(10, 600),
                    )

                    response.raise_for_status()
                    response = response.json()

                    content = response["choices"][0]["text"].strip()

                    if content:
                        break

                    log.info(f"[LOCALMODEL] empty content retry={retry+1}")

                if not content:
                    raise ValueError(f"[LOCALMODEL] empty content after retry | response={response}")

            result = content.strip()
            result = string_utils.cleanup_model_output(result)
            # log.info(f"[OPENROUTER] send_message success: elapsed={time.time() - started_at:.2f}s, length={len(result)}")

            log.info("[LOCALMODEL] 最終生成結果返答文字列：", result)
            return result

        except requests.exceptions.Timeout as e:
            log.info(f"[LOCALMODEL TIMEOUT] elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            log.info(f"[ERROR] LOCALMODEL request failed: elapsed={time.time() - started_at:.2f}s: {e}")
            if hasattr(e, "response") and e.response is not None:
                log.info(f"Status Code: {e.response.status_code}")
                try:
                    log.info(f"Response: {e.response.json()}")
                except Exception:
                    log.info(f"Response text: {e.response.text}")
            raise

        except (KeyError, IndexError, TypeError) as e:
            log.info(f"[ERROR] Failed to parse LOCALMODEL response: elapsed={time.time() - started_at:.2f}s: {e}")
            raise Exception(f"LOCALMODEL response parsing error: {e}")

        except Exception as e:
            log.info(f"[ERROR] Unexpected error in send_message: elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        finally:
            log.info(f"[LOCALMODEL] send_message finally")


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
            log.info("[WARN] OpenRouter APIキーが設定されていません。system_settings.yamlを確認してください。")

    def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        logit_bias: Optional[Dict[str, int]] = None,
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
            "logit_bias": {"248068": -100}, # <think> のトークンIDを抑制
            **kwargs
        }

        started_at = time.time()

        try:
            log.info(f"[OPENROUTER] send_message start: model={target_model}, started_at={started_at}")

            # log.info(f"[OPENROUTER] requests.post start: elapsed={time.time() - started_at:.2f}s")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=(10, 90)   # connect timeout, read timeout
            )
            # log.info(f"[OPENROUTER] requests.post end: elapsed={time.time() - started_at:.2f}s")
            log.info(f"[OPENROUTER] send_message end: model={target_model}, ended_at={time.time()}")

            # log.info(f"[OPENROUTER] raise_for_status start: elapsed={time.time() - started_at:.2f}s, status={response.status_code}")
            response.raise_for_status()
            # log.info(f"[OPENROUTER] raise_for_status end: elapsed={time.time() - started_at:.2f}s")

            # log.info(f"[OPENROUTER] response.json start: elapsed={time.time() - started_at:.2f}s")
            data = response.json()
            # log.info(f"[OPENROUTER] response.json end: elapsed={time.time() - started_at:.2f}s")

            if "choices" not in data:
                raise Exception(f"OpenRouter response missing 'choices': {data}")
            
            # log.info(f"[OPENROUTER] content extract start: elapsed={time.time() - started_at:.2f}s")
            
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

            # log.info(f"[OPENROUTER] content extract end: elapsed={time.time() - started_at:.2f}s")

            result = content.strip()
            # log.info(f"[OPENROUTER] send_message success: elapsed={time.time() - started_at:.2f}s, length={len(result)}")

            return result

        except requests.exceptions.Timeout as e:
            log.info(f"[OPENROUTER TIMEOUT] elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            log.info(f"[ERROR] OpenRouter API request failed: elapsed={time.time() - started_at:.2f}s: {e}")
            if hasattr(e, "response") and e.response is not None:
                log.info(f"Status Code: {e.response.status_code}")
                try:
                    log.info(f"Response: {e.response.json()}")
                except Exception:
                    log.info(f"Response text: {e.response.text}")
            raise

        except (KeyError, IndexError, TypeError) as e:
            log.info(f"[ERROR] Failed to parse OpenRouter response: elapsed={time.time() - started_at:.2f}s: {e}")
            raise Exception(f"OpenRouter response parsing error: {e}")

        except Exception as e:
            log.info(f"[ERROR] Unexpected error in send_message: elapsed={time.time() - started_at:.2f}s: {type(e).__name__}: {e}")
            raise

        finally:
            log.info(f"[OPENROUTER] send_message end")


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

def load_model(payload):
    base_path = payload.get("base_path") or ""

    if not base_path:
        return response_checker.response_error("ベースパスが未設定です。", status=400)

    full_path = Path(base_path) / "files" / "settings" / "system_settings.yaml"

    if not full_path.exists() or not full_path.is_file():
        return response_checker.response_error("ファイル読み込み失敗", status=404, full_path=str(full_path))

    try:
        # TODO:
        # ここを既存のモデルロード処理に差し替えてください。
        # 例:
        # global loaded_model
        # loaded_model = load_model_from_yaml(full_path)
        return response_checker.response_ok(message="ロード完了", full_path=str(full_path))
    except Exception as exc:
        return response_checker.response_error(f"モデルロード失敗しました。{exc}", status=500, full_path=str(full_path))

# stability matrix起動確認。入り口
def check_stability(payload):
    """Stability Matrixの起動確認（Silly Tavern改造対応）"""
    message = ""

    try:

        # Yamlの設定に変更があれば読み直しておく
        system_settings_reload_service.SystemSettingsReloadCheckService()

        result = True
        message = "起動してます。OK"

        result = False
        message = "起動してないよ。"

        return response_checker.response_ok(message=message)

    except Exception as e:
        log.info(f"[ERROR] check_stability: {e}")
        return response_checker.response_error(str(e), 500)
