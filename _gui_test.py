# -*- coding: utf-8 -*-
"""GUI 端到端测试 — 加载所有页面，抓取控制台错误与失败请求"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:5001'
PAGES = {
    '/dashboard':       ('audit-table-body', 'stat-total'),
    '/':                ('chatContainer', 'promptList'),
    '/admin':           ('panel-textbook', 'statsGrid'),
    '/kb-browser':      ('panel-vector', 'browseBody'),
    '/knowledge_base':  ('kb-table-body', None),
    '/settings':        ('providerTabs', 'panels'),
    '/agents':          ('agentGrid', None),
    '/teams':           ('teamGrid', None),
    '/teams/1':         ('chatMessages', 'memberList'),
    '/kg/explorer':     ('entity-list', 'chart'),
}

def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path, (el1, el2) in PAGES.items():
            page = browser.new_page()
            console_errors = []
            req_failures = []
            page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
            page.on('requestfailed', lambda r: req_failures.append(r.url))
            page.on('response', lambda r: req_failures.append(f'{r.status} {r.url}') if r.status >= 400 else None)
            try:
                page.goto(BASE + path, timeout=15000, wait_until='domcontentloaded')
                page.wait_for_timeout(3500)  # 等待 JS 数据加载
                el1_ok = page.locator(f'#{el1}').count() > 0 if el1 else True
                el2_ok = page.locator(f'#{el2}').count() > 0 if el2 else True
                # 统计表是否有数据行
                rows = page.locator(f'#{el1} tr').count() if el1 else 0
                results.append({
                    'path': path,
                    'status': 'OK',
                    'console_errors': console_errors[:5],
                    'req_failures': req_failures[:8],
                    'el1': el1_ok, 'el2': el2_ok, 'rows': rows,
                })
            except Exception as e:
                results.append({'path': path, 'status': 'EXCEPTION: ' + str(e)[:120], 'console_errors': console_errors[:5], 'req_failures': req_failures[:8], 'el1': False, 'el2': False, 'rows': 0})
            finally:
                page.close()
        browser.close()

    for r in results:
        print('=' * 70)
        print(f"[{r['status']}] {r['path']}  (el1={r['el1']}, el2={r['el2']}, rows={r['rows']})")
        if r['console_errors']:
            print('  CONSOLE ERRORS:')
            for e in r['console_errors']:
                print('   -', e[:180])
        if r['req_failures']:
            print('  REQUEST FAILURES:')
            for e in r['req_failures']:
                print('   -', e[:180])

if __name__ == '__main__':
    main()
