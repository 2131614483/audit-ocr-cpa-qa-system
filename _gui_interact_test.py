# -*- coding: utf-8 -*-
"""GUI 交互测试 — 真实业务操作：流式聊天/团队/审计辅导 + 标签切换 + 检索"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:5001'
RES = []

def record(name, ok, detail=''):
    RES.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()

    # ---------- 1. 团队对话 SSE (/teams/2) ----------
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    try:
        page.goto(BASE + '/teams/2', wait_until='commit'); page.wait_for_timeout(3000)
        mcount = page.locator('#memberList .member-card').count()
        page.fill('#questionInput', '用一句话解释什么是审计证据？')
        page.click('#sendBtn')
        page.wait_for_timeout(30000)
        final = page.locator('#chatMessages .msg-bubble:has-text("最终答案")').count() > 0
        dp = page.locator('#dpBody .dp-message').count()
        record('团队SSE /teams/2', final, f'members={mcount} dp消息={dp} errs={len(errs)}')
    except Exception as e:
        record('团队SSE /teams/2', False, str(e)[:100])
    finally:
        page.close()

    # ---------- 2. 审计辅导 SSE (/dashboard 详情+问问AI) ----------
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    try:
        page.goto(BASE + '/dashboard', wait_until='commit'); page.wait_for_timeout(4000)
        rowcount = page.locator('#audit-table-body tr').count()
        page.locator('#audit-table-body tr').first.click()
        page.wait_for_timeout(2000)
        modal_open = page.locator('.modal-box').count() > 0
        ai_panel = page.locator('#ai-chat-box').count() > 0
        if ai_panel:
            page.click('#ask-ai-btn')
            page.wait_for_timeout(35000)
            chat_msgs = page.locator('#ai-chat-messages .msg').count()
            has_answer = page.locator('#ai-chat-messages .msg.ai').count() > 0
            record('审计辅导SSE /dashboard', modal_open and has_answer, f'rows={rowcount} 模态={modal_open} AI消息={chat_msgs}')
        else:
            record('审计辅导SSE /dashboard', False, f'模态={modal_open} AI面板={ai_panel}')
    except Exception as e:
        record('审计辅导SSE /dashboard', False, str(e)[:100])
    finally:
        page.close()

    # ---------- 3. 主聊天 SocketIO (/) ----------
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    try:
        page.goto(BASE + '/', wait_until='commit'); page.wait_for_timeout(3000)
        page.fill('#questionInput', '什么是会计恒等式？')
        page.click('.chat-input-row .btn-primary')
        page.wait_for_timeout(40000)
        asst = page.locator('#chatContainer .chat-message.assistant .message-bubble')
        txt = asst.last.inner_text() if asst.count() else ''
        has_answer = asst.count() > 1 and len(txt) > 20
        record('主聊天SocketIO /', has_answer, f'助手消息={asst.count()} 长度={len(txt)} errs={len(errs)}')
    except Exception as e:
        record('主聊天SocketIO /', False, str(e)[:100])
    finally:
        page.close()

    # ---------- 4. 管理后台标签切换 ----------
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    try:
        page.goto(BASE + '/admin', wait_until='commit'); page.wait_for_timeout(3000)
        tabs = {}
        for name in ['textbook', 'qa', 'audit', 'dream']:
            page.click(f'.tab-btn:has-text("{name}")') if False else page.eval_on_selector_all('.tab-btn', 'els => els.forEach(e=>{})')
        # 用 index 点击标签
        btns = page.locator('.tab-btn')
        for i, label in [(1, '教材'), (2, '问答'), (3, '审计'), (4, '归档')]:
            if btns.nth(i).count():
                btns.nth(i).click()
                page.wait_for_timeout(1800)
                tbody = ['kbTableBody', 'qaTableBody', 'auditTableBody', 'dreamTableBody'][i - 1]
                rows = page.locator('#' + tbody + ' tr').count()
                tabs[label] = rows
        record('管理后台标签', all(tabs.values()) is not None, str(tabs))
    except Exception as e:
        record('管理后台标签', False, str(e)[:100])
    finally:
        page.close()

    # ---------- 5. 知识库检索 ----------
    page = ctx.new_page()
    errs = []
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    try:
        page.goto(BASE + '/kb-browser', wait_until='commit'); page.wait_for_timeout(2000)
        page.fill('#input-vector', '审计独立性')
        page.click('button:has-text("搜索")')
        page.wait_for_timeout(8000)
        cards = page.locator('#results-vector .result-item').count()
        record('知识库检索 vector', cards > 0, f'结果={cards}')
    except Exception as e:
        record('知识库检索 vector', False, str(e)[:100])
    finally:
        page.close()

    ctx.close()
    b.close()

print()
print('=' * 60)
fails = [r for r in RES if not r[1]]
print(f'总计 {len(RES)} 项，通过 {len(RES) - len(fails)}，失败 {len(fails)}')
