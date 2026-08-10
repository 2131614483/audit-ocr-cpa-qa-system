# ============================================================
# 统一模型调用入口
# 功能: 根据当前供应商路由到 Ollama 或 OpenAI 兼容 API，
#       支持文本/视觉模型调用，主模型/修复模型选择
# 核心: call_llm() - 统一入口，call_ollama_model() - Ollama调用
# ============================================================

import requests
import time
import json

from config.settings import cfg, load_model_config, get_provider_config
from utils.logger import write_simple_error_log


def _get_model_name(model_key: str = "main") -> str:
    """获取当前供应商下指定角色的模型名"""
    provider = get_provider_config()
    pcfg = provider["config"]
    models = pcfg.get("models", {})
    return models.get(model_key, cfg.MAIN_MODEL)


def _get_provider_info():
    """获取当前供应商信息"""
    return get_provider_config()


def call_llm(prompt: str, model_key: str = "main", image_base64: str = "") -> str:
    """
    统一模型调用入口

    参数:
        prompt: 提示词
        model_key: 模型角色 "main"/"fix"/"embed"
        image_base64: 图片base64（仅视觉模型支持）

    返回: 模型响应的文本
    """
    provider = get_provider_config()
    pname = provider["name"]
    pcfg = provider["config"]
    model_name = _get_model_name(model_key)
    api_url = pcfg.get("chat_api", "")
    api_key = pcfg.get("api_key", "")
    vision = pcfg.get("vision_support", False)
    timeout = getattr(cfg, "TIMEOUT", 300)

    if pname == "ollama":
        return _call_ollama(model_name, prompt, image_base64, api_url, timeout)
    else:
        return _call_openai_compat(pname, model_name, prompt, image_base64, api_url, api_key, vision, timeout)


def _call_ollama(model_name: str, prompt: str, image_base64: str, api_url: str, timeout: int) -> str:
    """调用 Ollama 原生 API"""
    reset_payload = {
        "model": model_name,
        "messages": [{"role": "system", "content": "清空所有对话历史，重置上下文"}],
        "options": {"num_ctx": 0},
        "stream": False
    }
    try:
        requests.post(api_url, json=reset_payload, timeout=timeout)
        if not hasattr(_call_ollama, "context_reset_logged"):
            write_simple_error_log("context_reset_success", "", f"成功清空{model_name}的上下文")
            _call_ollama.context_reset_logged = True
    except Exception as e:
        write_simple_error_log("context_reset_fail", "", f"清空上下文失败：{str(e)}")

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "stream": False,
        "max_tokens": 16384
    }
    if image_base64:
        payload["messages"][0]["images"] = [image_base64]

    try:
        response = requests.post(api_url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"].strip()
    except Exception as e:
        raise Exception(f"Ollama模型{model_name}调用失败：{str(e)}")


def _call_openai_compat(provider: str, model_name: str, prompt: str,
                        image_base64: str, api_url: str, api_key: str,
                        vision: bool, timeout: int) -> str:
    """调用 OpenAI 兼容格式的 API（DeepSeek/Qwen/OpenAI/Doubao）"""
    user_content = {"type": "text", "text": prompt}

    messages = [{"role": "user", "content": [user_content]}]

    if image_base64 and vision:
        data_uri = f"data:image/jpeg;base64,{image_base64}"
        content = [
            user_content,
            {"type": "image_url", "image_url": {"url": data_uri}}
        ]
        messages = [{"role": "user", "content": content}]

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 16384
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except requests.Timeout:
        raise Exception(f"{provider}模型{model_name}请求超时({timeout}秒)")
    except requests.HTTPError as e:
        status = e.response.status_code
        if status == 401:
            raise Exception(f"{provider}认证失败(401)，请检查 model_config.json 中的 api_key")
        elif status == 429:
            raise Exception(f"{provider}请求频率限制(429)，请稍后重试")
        else:
            raise Exception(f"{provider}模型{model_name}调用失败(HTTP {status})：{e.response.text[:200]}")
    except Exception as e:
        raise Exception(f"{provider}模型{model_name}调用失败：{str(e)}")


def call_ollama_model(model_name: str, prompt: str, image_base64: str = "") -> str:
    """兼容旧接口：直接指定模型名调用（用于 fix_json_with_deepseek 等）"""
    provider = get_provider_config()
    pmame = provider["name"]
    pcfg = provider["config"]
    api_url = pcfg.get("chat_api", "")
    api_key = pcfg.get("api_key", "")
    vision = pcfg.get("vision_support", False)
    timeout = getattr(cfg, "TIMEOUT", 300)

    if pmame == "ollama":
        return _call_ollama(model_name, prompt, image_base64, api_url, timeout)
    else:
        return _call_openai_compat(pmame, model_name, prompt, image_base64, api_url, api_key, vision, timeout)


def check_ollama_service() -> bool:
    """检查模型服务是否可用（Ollama 用 tags，云端用简单请求）"""
    provider = get_provider_config()
    pname = provider["name"]

    if pname == "ollama":
        try:
            requests.get("http://localhost:11434/api/tags", timeout=10)
            return True
        except Exception:
            return False
    else:
        pcfg = provider["config"]
        api_key = pcfg.get("api_key", "")
        api_url = pcfg.get("chat_api", "")
        if not api_key or "在此填入" in api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": _get_model_name("main"), "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1}
            r = requests.post(api_url, json=payload, headers=headers, timeout=15)
            return r.status_code < 500
        except Exception:
            return False


def check_models_available():
    """获取可用模型列表（仅 Ollama 支持列举模型）"""
    provider = get_provider_config()
    pname = provider["name"]

    if pname == "ollama":
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=10)
            return [m["name"] for m in response.json()["models"]]
        except Exception as e:
            write_simple_error_log("model_check_fail", "", f"检查模型失败：{str(e)}")
            return []
    else:
        return [_get_model_name("main"), _get_model_name("fix")]


def get_main_model() -> str:
    return _get_model_name("main")


def get_fix_model() -> str:
    return _get_model_name("fix")
