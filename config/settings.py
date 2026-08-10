# ============================================================
# 全局配置管理模块
# 功能: 单例模式加载 config.json 和 model_config.json，
#       提供全局配置对象 cfg，支持运行时切换模型供应商
# 核心: AppConfig（单例）、set_provider()、get_provider_config()
# ============================================================

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "data" / "config.json"
MODEL_CONFIG_FILE = Path(__file__).resolve().parent.parent / "data" / "model_config.json"

_default_config = {
    "MODEL_PROVIDER": "ollama",
    "OLLAMA_API_URL": "http://localhost:11434/api/chat",
    "MAIN_MODEL": "qwen3.5:latest",
    "FIX_MODEL": "deepseek-r1:8b",
    "IMAGE_FOLDER": "./input_pic",
    "EXCEL_OUTPUT": "./output/audit_ocr_result.xlsx",
    "OUTPUT_ROOT_FOLDER": "./output/分类结果",
    "ERROR_LOG_SIMPLE": "./output/ocr_error_simple.log",
    "RETRY_TASK_LOG": "./output/ocr_retry_tasks.log",
    "SUPPORTED_FORMATS": [".png", ".jpg", ".jpeg", ".webp", ".gif"],
    "RETRY_TIMES": 5,
    "FIX_RETRY_TIMES": 3,
    "PROCESS_RETRY_TIMES": 5,
    "TIMEOUT": 300,
    "EMBED_MODEL": "qwen3-embedding:8b",
    "KNOWLEDGE_BASE_PATH": "./knowledge/audit_knowledge_base.json",
    "DB_ENABLED": False,
    "DB_HOST": "localhost",
    "DB_PORT": 5432,
    "DB_NAME": "audit_ocr",
    "DB_USER": "postgres",
    "DB_PASSWORD": "admin",
}


def load_config(config_path: Path = None) -> dict:
    path = config_path or CONFIG_FILE
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            external = json.load(f)
        merged = _default_config.copy()
        merged.update(external)
        return merged
    return _default_config.copy()


def load_model_config() -> dict:
    if MODEL_CONFIG_FILE.exists():
        with open(MODEL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_provider": "ollama", "providers": {}}


_provider_override = None


def set_provider(provider_name: str):
    global _provider_override
    _provider_override = provider_name


def get_provider_config(override: str = None) -> dict:
    model_cfg = load_model_config()
    provider_name = override or _provider_override or load_config().get("MODEL_PROVIDER", "ollama")
    provider = model_cfg.get("providers", {}).get(provider_name, {})
    return {
        "name": provider_name,
        "config": provider,
    }


class AppConfig:
    _instance = None

    def __new__(cls, config_path: Path = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            raw = load_config(config_path)
            for k, v in raw.items():
                setattr(cls._instance, k, v)
        return cls._instance


cfg = AppConfig()
