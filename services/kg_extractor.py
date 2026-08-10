"""
CPA知识图谱 — 核心抽取器
============================================================
功能: 使用DeepSeek API从教材chunk中提取
  1. 实体（Concept/Standard/Formula/TaxItem/Question）
  2. 关系（9种类型）
  3. 计算公式
  4. 易混概念对
独立于现有代码，只依赖DeepSeek API + Ollama Embedding
============================================================
"""

import json
import os
import time
import sys
import requests
from typing import Optional
from pathlib import Path

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# ============================================================
# 配置加载
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_PATH = PROJECT_ROOT / "data" / "kg_prompts.json"
MODEL_CONFIG_PATH = PROJECT_ROOT / "data" / "model_config.json"


def load_prompts():
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_api_config():
    """加载当前供应商API配置（provider 用于区分 Ollama/OpenAI 兼容格式）"""
    if MODEL_CONFIG_PATH.exists():
        with open(MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        provider = cfg.get("current_provider", "deepseek")
        pcfg = cfg.get("providers", {}).get(provider, {})
        return {
            "provider": provider,
            "api_key": pcfg.get("api_key", ""),
            "api_url": pcfg.get("chat_api", "https://api.deepseek.com/v1/chat/completions"),
            "model": pcfg.get("models", {}).get("main", "deepseek-chat"),
        }
    return {"provider": "deepseek", "api_key": "", "api_url": "", "model": "deepseek-chat"}


def call_llm(system_prompt: str, user_prompt: str,
             temperature: float = 0.1, max_tokens: int = 3000) -> Optional[dict]:
    """调用DeepSeek API，返回解析后的JSON对象"""
    api_cfg = load_api_config()
    provider = api_cfg.get("provider", "deepseek")
    is_ollama = provider == "ollama"
    if not is_ollama and not api_cfg["api_key"]:
        print("[ERROR] API Key 未配置，请在 data/model_config.json 中设置")
        return None

    headers = {
        "Authorization": f"Bearer {api_cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": api_cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Ollama /api/chat 默认流式输出（NDJSON），必须显式关闭才能整包解析
        "stream": False,
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                api_cfg["api_url"],
                json=payload,
                headers=headers,
                timeout=300 if is_ollama else 60,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Ollama 返回 message.content；OpenAI 兼容返回 choices[0].message.content
                if is_ollama:
                    text = data.get("message", {}).get("content", "")
                else:
                    text = data["choices"][0]["message"]["content"]
                return _parse_json(text)
            else:
                print(f"  [WARN] API返回 {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [WARN] 第{attempt+1}次调用失败: {e}")
            time.sleep(2)
    return None


def _parse_json(text: str) -> Optional[dict]:
    """从LLM响应中提取第一个完整JSON对象（括号配平，忽略字符串内的花括号）"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    if end <= start:
        return None
    raw = text[start:end]
    # 尝试原样解析；失败则尝试修复单引号
    for attempt in (raw, raw.replace("'", '"')):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None


# ============================================================
# 核心抽取器
# ============================================================

class KnowledgeGraphExtractor:
    """CPA知识图谱抽取器"""

    def __init__(self):
        self.prompts = load_prompts()

    def _fill_template(self, template: str, **kwargs) -> str:
        """安全地填充模板，避免JSON花括号与format冲突"""
        result = template
        for key, value in kwargs.items():
            result = result.replace("{" + key + "}", str(value))
        return result

    # ---- 1. 实体抽取 ----

    def extract_entities(self, chunk_text: str, chapter_info: str = "") -> list[dict]:
        """从chunk中提取结构化实体"""
        prompt_cfg = self.prompts["entity_extraction"]
        user_prompt = self._fill_template(
            prompt_cfg["user_prompt_template"],
            chunk_text=chunk_text[:3000],
            chapter_info=chapter_info or "未知",
        )
        result = call_llm(
            prompt_cfg["system_prompt"],
            user_prompt,
            temperature=prompt_cfg["temperature"],
            max_tokens=prompt_cfg["max_tokens"],
        )
        if result and "entities" in result:
            entities = result["entities"]
            # 过滤和规范化
            valid = []
            for e in entities:
                name = (e.get("name") or "").strip()
                if not name or len(name) < 2 or len(name) > 100:
                    continue
                e["name"] = name
                e.setdefault("entity_type", "Concept")
                e.setdefault("category", "其他")
                e.setdefault("definition", name)
                e.setdefault("chapter_ref", chapter_info)
                e.setdefault("importance", "中")
                valid.append(e)
            return valid
        return []

    # ---- 2. 关系抽取 ----

    def extract_relationships(self, entities: list[dict],
                              chunk_text: str) -> list[dict]:
        """从chunk中提取实体间关系"""
        if len(entities) < 2:
            return []

        # 精简实体信息发给LLM
        entity_summary = [
            {"name": e["name"], "entity_type": e.get("entity_type", "Concept"),
             "definition": e.get("definition", "")[:80]}
            for e in entities[:30]  # 最多30个实体
        ]

        prompt_cfg = self.prompts["relation_extraction"]
        user_prompt = self._fill_template(
            prompt_cfg["user_prompt_template"],
            entities_json=json.dumps(entity_summary, ensure_ascii=False, indent=2),
            chunk_text=chunk_text[:3000],
        )
        result = call_llm(
            prompt_cfg["system_prompt"],
            user_prompt,
            temperature=prompt_cfg["temperature"],
            max_tokens=prompt_cfg["max_tokens"],
        )
        if result and "relationships" in result:
            rels = result["relationships"]
            valid = []
            valid_types = {
                "derives_from", "references", "contrasts_with",
                "prerequisite_of", "composes", "leads_to",
                "belongs_to", "tested_by", "similar_to",
            }
            for r in rels:
                source = (r.get("source") or "").strip()
                target = (r.get("target") or "").strip()
                if not source or not target or source == target:
                    continue
                rt = r.get("relation_type", "references")
                if rt not in valid_types:
                    rt = "references"
                r["source"] = source
                r["target"] = target
                r["relation_type"] = rt
                r.setdefault("description", f"{source}与{target}存在{rt}关系")
                r.setdefault("formula", None)
                r.setdefault("confidence", 0.5)
                valid.append(r)
            return valid
        return []

    # ---- 3. 公式抽取 ----

    def extract_formulas(self, chunk_text: str,
                         chapter_info: str = "") -> list[dict]:
        """从chunk中提取计算公式"""
        prompt_cfg = self.prompts["formula_extraction"]
        user_prompt = self._fill_template(
            prompt_cfg["user_prompt_template"],
            chunk_text=chunk_text[:3000],
            chapter_info=chapter_info or "未知",
        )
        result = call_llm(
            prompt_cfg["system_prompt"],
            user_prompt,
            temperature=prompt_cfg["temperature"],
            max_tokens=prompt_cfg["max_tokens"],
        )
        if result and "formulas" in result:
            formulas = result["formulas"]
            valid = []
            for f in formulas:
                name = (f.get("name") or "").strip()
                expr = (f.get("expression") or "").strip()
                if not name or not expr:
                    continue
                f.setdefault("inputs", [])
                f.setdefault("output", "")
                f.setdefault("conditions", "")
                f.setdefault("example", "")
                valid.append(f)
            return valid
        return []

    # ---- 4. 易混概念识别 ----

    def detect_confusion_pairs(self, entities: list[dict],
                               chunk_text: str) -> list[dict]:
        """识别易混概念对"""
        if len(entities) < 2:
            return []

        entity_summary = [
            {"name": e["name"], "entity_type": e.get("entity_type", "Concept"),
             "definition": e.get("definition", "")[:80]}
            for e in entities[:30]
        ]

        prompt_cfg = self.prompts["confusion_detection"]
        user_prompt = self._fill_template(
            prompt_cfg["user_prompt_template"],
            entities_json=json.dumps(entity_summary, ensure_ascii=False, indent=2),
            chunk_text=chunk_text[:3000],
        )
        result = call_llm(
            prompt_cfg["system_prompt"],
            user_prompt,
            temperature=prompt_cfg["temperature"],
            max_tokens=prompt_cfg["max_tokens"],
        )
        if result and "confusion_pairs" in result:
            pairs = result["confusion_pairs"]
            valid = []
            for p in pairs:
                a = (p.get("concept_a") or "").strip()
                b = (p.get("concept_b") or "").strip()
                if not a or not b or a == b:
                    continue
                p.setdefault("distinction", f"{a}与{b}的区别需要结合具体场景分析")
                p.setdefault("scenario_a", "")
                p.setdefault("scenario_b", "")
                p.setdefault("typical_question", "")
                valid.append(p)
            return valid
        return []

    # ---- 综合处理一个chunk ----

    def process_chunk(self, chunk_text: str, chapter_info: str = "",
                      stages: set = None) -> dict:
        """
        对一个chunk执行全部抽取
        stages: 可选 {"entities", "relationships", "formulas", "confusions"}
        """
        if stages is None:
            stages = {"entities", "relationships", "formulas", "confusions"}

        result = {
            "entities": [],
            "relationships": [],
            "formulas": [],
            "confusion_pairs": [],
        }

        chunk_text = chunk_text.strip()
        if len(chunk_text) < 50:
            return result

        if "entities" in stages:
            result["entities"] = self.extract_entities(chunk_text, chapter_info)

        if "relationships" in stages and result["entities"]:
            result["relationships"] = self.extract_relationships(
                result["entities"], chunk_text
            )

        if "formulas" in stages:
            result["formulas"] = self.extract_formulas(chunk_text, chapter_info)

        if "confusions" in stages and result["entities"]:
            result["confusion_pairs"] = self.detect_confusion_pairs(
                result["entities"], chunk_text
            )

        return result
