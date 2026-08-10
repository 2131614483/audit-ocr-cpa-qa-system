# -*- coding: utf-8 -*-
"""REST API 全量扫描 — 报告 4xx/5xx/异常与响应结构"""
import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = 'http://localhost:5001'
results = []

def check(name, method, path, body=None, expect_keys=None, timeout=60):
    try:
        r = requests.request(method, BASE + path, json=body, timeout=timeout)
        data = None
        try: data = r.json()
        except Exception: pass
        ok = r.status_code < 400
        keys = ''
        if expect_keys and isinstance(data, dict):
            missing = [k for k in expect_keys if k not in data]
            keys = f' 缺失字段={missing}' if missing else ''
        tag = 'OK' if ok else '!!!'
        print(f'[{tag}] {name} {method} {path} -> {r.status_code}{keys}')
        if not ok:
            print(f'        resp: {str(data)[:180] if data else r.text[:180]}')
        results.append((name, ok))
        return data
    except Exception as e:
        print(f'[XXX] {name} {method} {path} -> EXCEPTION {str(e)[:120]}')
        results.append((name, False))
        return None

print('======= 审计看板 =======')
check('审计数据', 'GET', '/api/audit_data')
check('统计', 'GET', '/api/statistics', expect_keys=['total_records','risk_distribution','type_distribution'])
check('单记录', 'GET', '/api/audit_record/1')
check('知识库单条', 'GET', '/api/knowledge_base/1')
check('知识库批量', 'GET', '/api/knowledge_base/batch?ids=1,2')
check('全部知识库', 'GET', '/api/all_knowledge_base')

print('======= CPA 知识库 =======')
check('检索vector', 'POST', '/api/cpa_knowledge/search', {'query':'审计独立性','mode':'vector','top_k':5})
check('检索bm25', 'POST', '/api/cpa_knowledge/search', {'query':'审计独立性','mode':'bm25','top_k':5})
check('检索hybrid', 'POST', '/api/cpa_knowledge/search', {'query':'审计独立性','mode':'hybrid','top_k':5})
check('检索graph', 'POST', '/api/cpa_knowledge/search', {'query':'审计独立性','mode':'graph','top_k':5})
check('知识库列表', 'POST', '/api/cpa_knowledge/list', {'page':1,'page_size':5,'search':''})
check('知识库详情', 'POST', '/api/cpa_knowledge/detail', {'id':1})
check('知识库统计', 'GET', '/api/cpa_knowledge/stats', expect_keys=['type_stats'])
check('教材列表', 'GET', '/api/cpa_knowledge/books', expect_keys=['books'])

print('======= 问答历史 =======')
check('历史列表', 'POST', '/api/cpa_qa_history/list', {'page':1,'page_size':5,'search':''})
check('历史详情', 'POST', '/api/cpa_qa_history/detail', {'id':1})

print('======= Dream 做梦 =======')
check('状态', 'GET', '/api/dream/status')
check('分类', 'GET', '/api/dream/knowledge/categories')
check('列表', 'POST', '/api/dream/knowledge/list', {'page':1,'page_size':5,'search':'','category':''})

print('======= Agent / 团队 =======')
check('Agent列表', 'GET', '/api/agents/list')
check('团队列表', 'GET', '/api/teams/list')

print('======= 配置 =======')
check('模型配置', 'GET', '/api/config/get', expect_keys=['config'])
check('系统配置', 'GET', '/api/system_config/get', expect_keys=['config'])
check('提示词配置', 'GET', '/api/prompts/get', expect_keys=['prompts','skills'])

print('======= 统计 / 教材 =======')
check('总统计', 'GET', '/api/stats')
check('教材books', 'GET', '/api/books/list', expect_keys=['books'])

print('======= 知识图谱 =======')
check('库内图谱统计', 'GET', '/api/graph/stats')
check('图谱库统计', 'GET', '/api/kg/stats', expect_keys=['entity_count'])
check('图谱实体', 'GET', '/api/kg/entities?page_size=5', expect_keys=['entities'])
check('图谱关系', 'GET', '/api/kg/relations?limit=10', expect_keys=['relations'])

print()
fails = [n for n, ok in results if not ok]
print(f'扫描 {len(results)} 项，失败 {len(fails)} 项: {fails if fails else "无"}')
