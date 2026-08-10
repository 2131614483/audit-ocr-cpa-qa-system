# ============================================================
# CPA 知识库问答 - CLI 版本
# 版本: 20260514
# 最后更新: 2026-05-14
# 功能: 命令行问答，向量检索+DeepSeek API
# ============================================================

# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
"""
CPA知识库问答系统
功能：
1. 基于向量相似度检索知识库
2. 调用DeepSeek API生成回答
3. 支持引用知识库来源

使用方法：
    python cpa_qa.py "什么是资产负债表？"
    或
    python cpa_qa.py  # 交互式问答

API Key: sk-646f6bb5863d4c18a1567a96ce8f28ce
"""

import os
import sys
import json
import psycopg2
import requests
import numpy as np
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cpazs.config_cpa import DB_CONFIG, EMBEDDING_CONFIG

# DeepSeek配置
DEEPSEEK_API_KEY = "sk-646f6bb5863d4c18a1567a96ce8f28ce"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def get_embedding(text):
    """获取文本的embedding"""
    if not text or not text.strip():
        return None
    
    # 优先使用本地Ollama
    if EMBEDDING_CONFIG.get("provider") == "ollama":
        try:
            r = requests.post(
                EMBEDDING_CONFIG.get("api_url", "http://localhost:11434/api/embeddings"),
                json={"model": EMBEDDING_CONFIG.get("model", "qwen3-embedding:0.6b"), "prompt": text.strip()},
                timeout=60
            )
            r.raise_for_status()
            data = r.json()
            if "embedding" in data:
                return data["embedding"]
        except Exception as e:
            print(f"⚠️ 本地Ollama调用失败，使用DeepSeek: {e}")
    
    # 备用：使用DeepSeek Embedding
    try:
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        r = requests.post(
            "https://api.deepseek.com/v1/embeddings",
            json={"model": "text-embedding-3-large", "input": text.strip()},
            headers=headers,
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
    except Exception as e:
        print(f"❌ Embedding生成失败: {e}")
    
    return None

def cosine_similarity(vec_a, vec_b):
    """计算余弦相似度"""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def search_knowledge(query, top_k=5):
    """在知识库中搜索相关内容"""
    print(f"🔍 正在搜索知识库...")
    
    # 获取查询的embedding
    query_embedding = get_embedding(query)
    if not query_embedding:
        print("❌ 无法生成查询向量")
        return []
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 查询所有向量
    cur.execute("SELECT id, source_type, source_id, chunk_content, embedding, metadata FROM cpa_embeddings WHERE embedding IS NOT NULL")
    
    results = []
    for row in cur.fetchall():
        emb_id, source_type, source_id, content, embedding_bytes, metadata = row
        
        try:
            # 将二进制embedding转换为列表
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32).tolist()
            similarity = cosine_similarity(query_embedding, embedding)
            
            # 解析metadata
            meta_info = {}
            if metadata:
                try:
                    meta_info = json.loads(metadata)
                except:
                    pass
            
            results.append({
                "id": emb_id,
                "source_type": source_type,
                "source_id": source_id,
                "content": content[:500] if content else "",
                "similarity": similarity,
                "metadata": meta_info
            })
        except Exception as e:
            continue
    
    conn.close()
    
    # 按相似度排序
    results.sort(key=lambda x: x["similarity"], reverse=True)
    
    print(f"✅ 找到 {len(results)} 条匹配结果，返回前{top_k}条")
    return results[:top_k]

def call_deepseek_api(prompt):
    """调用DeepSeek API生成回答"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是一名专业的注册会计师考试辅导专家，请根据提供的知识库内容回答问题。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        r = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=120)
        r.raise_for_status()
        data = r.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        
        return None
    except Exception as e:
        print(f"❌ DeepSeek API调用失败: {e}")
        return None

def generate_answer(query):
    """生成回答"""
    print(f"\n🤔 用户问题: {query}")
    
    # 搜索知识库
    search_results = search_knowledge(query)
    
    if not search_results:
        print("⚠️ 知识库中未找到相关内容，直接回答")
        answer = call_deepseek_api(query)
        if answer:
            print(f"\n📝 回答:\n{answer}")
        return
    
    # 构建上下文
    context = ""
    sources = []
    
    for i, result in enumerate(search_results, 1):
        content = result["content"]
        similarity = result["similarity"]
        meta = result["metadata"]
        
        context += f"【参考资料{i}】\n"
        context += f"相似度: {similarity:.4f}\n"
        if meta:
            context += f"来源: {meta.get('book_name', '')} - 第{meta.get('chapter_number', '')}章\n"
        context += f"内容: {content}\n\n"
        
        sources.append({
            "index": i,
            "similarity": similarity,
            "book": meta.get('book_name', ''),
            "chapter": meta.get('chapter_number', '')
        })
    
    # 构建prompt
    prompt = f"""
基于以下知识库内容，回答用户问题：

{context}

用户问题：{query}

要求：
1. 优先使用知识库中的信息进行回答
2. 如果知识库内容不足，可以补充你的专业知识
3. 回答要清晰、准确，结构合理
4. 最后列出参考来源
"""
    
    # 调用DeepSeek API
    print("🔄 正在生成回答...")
    answer = call_deepseek_api(prompt)
    
    if answer:
        print(f"\n📝 回答:\n{answer}")
        
        # 打印来源列表
        print("\n📚 参考来源:")
        for src in sources:
            print(f"  [{src['index']}] {src['book']} - 第{src['chapter']}章 (相似度: {src['similarity']:.2%})")
    
    return answer

def interactive_mode():
    """交互式问答模式"""
    print("=" * 60)
    print("💬 CPA知识库问答系统")
    print("=" * 60)
    print("输入问题进行问答，输入 'exit' 退出")
    print("-" * 60)
    
    while True:
        query = input("\n请输入问题: ")
        if query.lower() == 'exit':
            print("👋 再见！")
            break
        
        if not query.strip():
            continue
        
        generate_answer(query)

if __name__ == "__main__":
    # 检查DeepSeek连接
    print("📡 正在测试DeepSeek连接...")
    try:
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        r = requests.post(
            DEEPSEEK_API_URL,
            json={"model": DEEPSEEK_MODEL, "messages": [{"role": "user", "content": "hello"}]},
            headers=headers,
            timeout=30
        )
        r.raise_for_status()
        print("✅ DeepSeek连接成功")
    except Exception as e:
        print(f"❌ DeepSeek连接失败: {e}")
        sys.exit(1)
    
    # 检查知识库数据
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cpa_embeddings")
    emb_count = cur.fetchone()[0]
    conn.close()
    print(f"📊 知识库向量数: {emb_count}")
    
    # 如果有命令行参数，直接回答
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        generate_answer(query)
    else:
        # 进入交互式模式
        interactive_mode()