# ============================================================
# CPA 知识库导入配置
# 版本: 20260514
# 最后更新: 2026-05-14
# 功能: DB/Embedding/Chunk配置，23本教材数据源列表
# ============================================================

"""
CPA知识库导入配置
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "cpa_knowledge",
    "user": "postgres",
    "password": "admin"
}

EMBEDDING_CONFIG = {
    "model": "qwen3-embedding:0.6b",
    "dimension": 1024,
    "provider": "ollama",
    "api_url": "http://localhost:11434/api/embeddings"
}

CHUNK_CONFIG = {
    "chunk_size": 600,
    "chunk_overlap": 100,
    "min_chunk_length": 0
}

DATA_SOURCES = [
    # ========== 官方教材 (6本) ==========
    {
        "path": "2026年注册会计师（会计）官方教材/auto",
        "course_code": "KJ",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（会计）官方教材"
    },
    {
        "path": "2026年注册会计师（审计）/auto",
        "course_code": "SJ",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（审计）"
    },
    {
        "path": "2026年注册会计师（税法）/auto",
        "course_code": "SF",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（税法）"
    },
    {
        "path": "2026年注册会计师1（财务成本管理）/auto",
        "course_code": "CW",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（财务成本管理）"
    },
    {
        "path": "2026年注册会计师（经济法）/auto",
        "course_code": "JJ",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（经济法）"
    },
    {
        "path": "2026年注册会计师（公司战略与风险管理）/auto",
        "course_code": "ZZ",
        "book_type": "官方教材",
        "book_name": "2026年注册会计师（公司战略与风险管理）"
    },
    
    # ========== 会计轻一 (3本) ==========
    {
        "path": "会计轻一（上册） (OCR)/ocr",
        "course_code": "KJ",
        "book_type": "轻一",
        "book_name": "会计轻一（上册）"
    },
    {
        "path": "会计轻一（中册） (OCR)/ocr",
        "course_code": "KJ",
        "book_type": "轻一",
        "book_name": "会计轻一（中册）"
    },
    {
        "path": "会计轻一（下册） (OCR)/ocr",
        "course_code": "KJ",
        "book_type": "轻一",
        "book_name": "会计轻一（下册）"
    },
    
    # ========== 审计轻一 (3本) ==========
    {
        "path": "审计轻一（上册） (OCR)/ocr",
        "course_code": "SJ",
        "book_type": "轻一",
        "book_name": "审计轻一（上册）"
    },
    {
        "path": "审计轻一（中册） (OCR)/ocr",
        "course_code": "SJ",
        "book_type": "轻一",
        "book_name": "审计轻一（中册）"
    },
    {
        "path": "审计轻一（下册） (OCR)/ocr",
        "course_code": "SJ",
        "book_type": "轻一",
        "book_name": "审计轻一（下册）"
    },
    
    # ========== 税法轻一 (3本) ==========
    {
        "path": "税法轻一（上册） (OCR)/ocr",
        "course_code": "SF",
        "book_type": "轻一",
        "book_name": "税法轻一（上册）"
    },
    {
        "path": "税法轻一（中册） (OCR)/ocr",
        "course_code": "SF",
        "book_type": "轻一",
        "book_name": "税法轻一（中册）"
    },
    {
        "path": "税法轻一（下册） (OCR)/ocr",
        "course_code": "SF",
        "book_type": "轻一",
        "book_name": "税法轻一（下册）"
    },
    
    # ========== 财管轻一 (3本) ==========
    {
        "path": "财管轻一（上册） (OCR)/ocr",
        "course_code": "CW",
        "book_type": "轻一",
        "book_name": "财管轻一（上册）"
    },
    {
        "path": "财管轻一（中册） (OCR)/ocr",
        "course_code": "CW",
        "book_type": "轻一",
        "book_name": "财管轻一（中册）"
    },
    {
        "path": "财管轻一（下册） (OCR)/ocr",
        "course_code": "CW",
        "book_type": "轻一",
        "book_name": "财管轻一（下册）"
    },
    
    # ========== 经济法轻一 (3本) ==========
    {
        "path": "经济法轻一（上册） (OCR)/ocr",
        "course_code": "JJ",
        "book_type": "轻一",
        "book_name": "经济法轻一（上册）"
    },
    {
        "path": "经济法轻一（中册） (OCR)/ocr",
        "course_code": "JJ",
        "book_type": "轻一",
        "book_name": "经济法轻一（中册）"
    },
    {
        "path": "经济法轻一（下册） (OCR)/ocr",
        "course_code": "JJ",
        "book_type": "轻一",
        "book_name": "经济法轻一（下册）"
    },
    
    # ========== 战略轻一 (2本) ==========
    {
        "path": "战略轻一（上册）（OCR)/ocr",
        "course_code": "ZZ",
        "book_type": "轻一",
        "book_name": "战略轻一（上册）"
    },
    {
        "path": "战略轻一（下册） (OCR)/ocr",
        "course_code": "ZZ",
        "book_type": "轻一",
        "book_name": "战略轻一（下册）"
    }
]

HEADING_PATTERNS = {
    "chapter": r"^#\s+(第[一二三四五六七八九十百千]+章|第一章|第二章|...)",
    "section": r"^##\s+第?[一二三四五六七八九十百千]+节",
    "subsection": r"^###\s+",
    "content": r"^####\s+"
}

print(f"📚 已配置 {len(DATA_SOURCES)} 本教材")