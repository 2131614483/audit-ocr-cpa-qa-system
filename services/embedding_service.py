# ============================================================
# 向量生成服务
# 功能: 调用 Ollama 或云端 API 生成文本向量，
#       支持余弦相似度计算
# 核心: get_embedding() - 向量生成
#       cosine_similarity() - 相似度计算
# ============================================================

import requests
import time

from config.settings import cfg, get_provider_config
from utils.logger import write_simple_error_log


def get_embed_model() -> str:
    provider = get_provider_config()
    pcfg = provider["config"]
    models = pcfg.get("models", {})
    return models.get("embed", "") or getattr(cfg, "EMBED_MODEL", "qwen3-embedding:0.6b")


def get_embedding(text: str) -> list | None:
    if not text or not text.strip():
        return None

    provider = get_provider_config()
    pname = provider["name"]
    pcfg = provider["config"]
    embed_api = pcfg.get("embed_api", "")
    api_key = pcfg.get("api_key", "")
    model_name = get_embed_model()

    if not embed_api:
        write_simple_error_log("embedding_no_api", "", f"{pname}[{pcfg.get('name','')}] 未配置 embedding API")
        return None

    if pname == "ollama":
        return _get_embedding_ollama(model_name, text, embed_api)
    else:
        return _get_embedding_openai(pname, model_name, text, embed_api, api_key)


def _get_embedding_ollama(model: str, text: str, api_url: str) -> list | None:
    payload = {"model": model, "input": text.strip()}
    for retry in range(3):
        try:
            r = requests.post(api_url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
            raise ValueError(f"响应中无embedding: {data}")
        except Exception as e:
            if retry < 2:
                time.sleep(3)
                continue
            write_simple_error_log("embedding_fail", "", f"Ollama embedding失败: {str(e)}")
            return None


def _get_embedding_openai(provider: str, model: str, text: str, api_url: str, api_key: str) -> list | None:
    """OpenAI 兼容格式的 embedding API（支持 OpenAI / DeepSeek / Qwen / Doubao）"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": text.strip()}

    # DeepSeek 用不同维度的模型名
    if provider == "deepseek":
        payload["encoding_format"] = "float"

    for retry in range(3):
        try:
            r = requests.post(api_url, json=payload, headers=headers, timeout=120)
            r.raise_for_status()
            data = r.json()

            # OpenAI 格式: data[0].embedding
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            # Ollama 格式兜底
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]

            raise ValueError(f"无法解析embedding响应: {list(data.keys())}")
        except requests.HTTPError as e:
            status = e.response.status_code
            if status == 401:
                write_simple_error_log("embedding_auth_fail", "", f"{provider}认证失败(401)，请检查 api_key")
                return None
            if retry < 2:
                time.sleep(3)
                continue
            write_simple_error_log("embedding_fail", "", f"{provider} embedding失败(HTTP {status})")
            return None
        except Exception as e:
            if retry < 2:
                time.sleep(3)
                continue
            write_simple_error_log("embedding_fail", "", f"{provider} embedding失败: {str(e)}")
            return None


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
