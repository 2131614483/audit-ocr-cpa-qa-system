# 控制台输出强制 UTF-8（Windows GBK 控制台无法打印 emoji，会导致启动崩溃）
import sys as _s
if hasattr(_s.stdout, 'reconfigure'):
    _s.stdout.reconfigure(encoding='utf-8', errors='replace')
    _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import json
import time
import queue
import threading
import requests
import psycopg2
from datetime import datetime

DB_CONFIG = {"host": "localhost", "port": 5432, "dbname": "cpa_knowledge", "user": "postgres", "password": "admin"}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def call_llm(prompt, context="", history=None, model=None):
    from services.ollama_client import call_llm as _call_llm_central
    full_prompt = prompt
    if context:
        full_prompt = f"{prompt}\n\n上下文信息：\n{context}"
    if history:
        full_prompt += "\n\n历史对话：\n" + "\n".join([f"{m['role']}: {m['content']}" for m in history])
    full_prompt += "\n\n请根据以上信息进行分析和回答。"
    try:
        return _call_llm_central(full_prompt, model_key="main")
    except Exception as e:
        print(f"[orchestrator] LLM调用失败: {e}")
        return None

SYSTEM_PROMPTS = {
    "sequential_summarizer": "你是一个团队协作汇总专家。请将多个专家按顺序分析的结果整合成一份连贯、完整的最终回答。要求：1)保留每个专家的核心观点;2)消除重复内容;3)按逻辑顺序组织;4)标注每个部分的贡献专家。",
    "parallel_summarizer": "你是一个多角度分析汇总专家。以下是从不同角度对同一问题的分析结果，请整合成一份全面的回答。要求：1)保留每个角度的独特见解;2)指出各角度的一致点和差异点;3)给出综合结论。",
    "debate_moderator": "你是一个辩论主持专家。以下是多位专家就同一问题的辩论过程，请进行裁决。要求：1)总结各方核心论点;2)指出论据的强弱;3)给出最终裁决结论。"
}

def run_team(team_id, question, session_id=""):
    from services.team_service import get_team
    team = get_team(team_id)
    if not team:
        return {"error": "团队不存在"}
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO cpa_workflow_runs (session_id, team_id, question, status) VALUES (%s, %s, %s, 'running') RETURNING id",
                (session_id, team_id, question))
    workflow_id = cur.fetchone()[0]
    conn.commit()
    try:
        wt = team["workflow_type"]
        if wt == "sequential":
            result = _run_sequential(workflow_id, team, question, cur, conn, None)
        elif wt == "parallel":
            result = _run_parallel(workflow_id, team, question, cur, conn, None)
        elif wt == "debate":
            result = _run_debate(workflow_id, team, question, cur, conn, None)
        else:
            result = _run_sequential(workflow_id, team, question, cur, conn, None)
        cur.execute("UPDATE cpa_workflow_runs SET status='done', final_answer=%s, finished_at=NOW() WHERE id=%s", (result, workflow_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"answer": result, "workflow_id": workflow_id}
    except Exception as e:
        cur.execute("UPDATE cpa_workflow_runs SET status='failed', finished_at=NOW() WHERE id=%s", (workflow_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"error": str(e)}

def _save_step(cur, workflow_id, step_order, agent_id, agent_name, input_text, output_text, decision=""):
    cur.execute("""INSERT INTO cpa_workflow_steps (workflow_id, step_order, agent_id, agent_name, input_text, output_text, decision)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (workflow_id, step_order, agent_id, agent_name, input_text, output_text, decision))

def _run_sequential(workflow_id, team, question, cur, conn, cb):
    current_input = question
    members = team["members"]
    model = team.get("model_override") or None
    custom_prompt = team.get("custom_prompt", "")
    for idx, member in enumerate(members):
        agent_name = member.get("display_name") or member.get("agent_name", f"Agent#{member['agent_id']}")
        role = member.get("role_in_team", "")
        task_rules = member.get("task_rules", "")
        if cb: cb("agent_start", {"agent": agent_name, "order": idx+1, "total": len(members), "mode": "sequential", "role": role})
        context = f"原始问题：{question}"
        if idx > 0:
            context = f"前面的分析结果：\n{current_input}\n\n原始问题：{question}"
        prompt = f"你是一名{agent_name}。职责：{role}\n请基于你的专业知识进行分析。"
        if task_rules:
            prompt += f"\n\n【自定义任务规则】\n{task_rules}"
        if custom_prompt:
            prompt += f"\n\n【团队自定义指令】\n{custom_prompt}"
        output = call_llm(prompt, context=context, model=model)
        if not output: output = f"（{agent_name}暂时无法分析）"
        _save_step(cur, workflow_id, idx+1, member["agent_id"], agent_name, current_input[:500], output)
        conn.commit()
        if cb: cb("agent_output", {"agent": agent_name, "output": output, "order": idx+1})
        current_input = f"【{agent_name}的分析】\n{output}"
    if cb: cb("summarizing", {"message": "所有专家已完成分析，正在汇总..."})
    final = call_llm(SYSTEM_PROMPTS["sequential_summarizer"], context=f"问题：{question}\n\n各专家分析：\n{current_input}", model=model)
    return final or current_input

def _run_parallel(workflow_id, team, question, cur, conn, cb):
    members = team["members"]
    max_rounds = team.get("max_rounds", 3)
    model = team.get("model_override") or None
    custom_prompt = team.get("custom_prompt", "")
    all_round_outputs = []
    db_lock = threading.Lock()

    def call_agent(member, round_num, previous_context):
        agent_name = member.get("display_name") or member.get("agent_name", f"Agent#{member['agent_id']}")
        role = member.get("role_in_team", "")
        task_rules = member.get("task_rules", "")
        base_prompt = f"你是一名{agent_name}。职责：{role}\n"
        if task_rules:
            base_prompt += f"\n\n【自定义任务规则】\n{task_rules}"
        if custom_prompt:
            base_prompt += f"\n\n【团队自定义指令】\n{custom_prompt}"
        if round_num == 0:
            prompt = base_prompt + "\n请从你的专业角度分析以下问题，给出独立见解。"
            output = call_llm(prompt, context=f"问题：{question}", model=model)
        else:
            prompt = base_prompt + "\n请基于其他专家前一轮的分析，补充、反驳或修正你的观点。"
            output = call_llm(prompt, context=f"问题：{question}\n\n其他专家的前一轮分析：\n{previous_context}", model=model)
        if not output:
            output = f"（{agent_name}在第{round_num+1}轮无法分析）"
        return agent_name, output

    for round_num in range(max_rounds):
        if cb: cb("summarizing", {"message": f"📢 第{round_num+1}轮并行讨论开始..."})
        round_outputs = [None] * len(members)

        def worker(idx, member):
            previous = ""
            if round_num > 0 and all_round_outputs:
                for prev_name, prev_out in all_round_outputs[round_num - 1]:
                    previous += f"=== {prev_name} 第{round_num}轮分析 ===\n{prev_out}\n\n"
            name, out = call_agent(member, round_num, previous)
            round_outputs[idx] = (name, out)
            step_order = round_num * len(members) + idx + 1
            with db_lock:
                _save_step(cur, workflow_id, step_order, member["agent_id"], name,
                           question[:300], out, decision=f"第{round_num+1}轮")
                conn.commit()

        threads = []
        for idx, member in enumerate(members):
            t = threading.Thread(target=worker, args=(idx, member), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        for idx, member in enumerate(members):
            agent_name = member.get("display_name") or member.get("agent_name", f"Agent#{member['agent_id']}")
            if cb: cb("agent_start", {"agent": agent_name, "order": idx+1, "total": len(members), "mode": "parallel", "role": member.get("role_in_team", ""), "round": round_num+1})
            if cb: cb("agent_output", {"agent": round_outputs[idx][0], "output": round_outputs[idx][1], "order": round_num * len(members) + idx + 1, "round": round_num+1})
        all_round_outputs.append(round_outputs)

    if cb: cb("summarizing", {"message": "所有轮次讨论完成，正在汇总..."})
    context = f"问题：{question}\n\n"
    for r_idx, round_data in enumerate(all_round_outputs):
        context += f"【第{r_idx+1}轮讨论】\n"
        for name, out in round_data:
            context += f"=== {name} ===\n{out}\n\n"
    final = call_llm(SYSTEM_PROMPTS["parallel_summarizer"], context=context, model=model)
    return final or context

def _run_debate(workflow_id, team, question, cur, conn, cb):
    members = team["members"]
    max_rounds = team.get("max_rounds", 3)
    debate_log = []
    model = team.get("model_override") or None
    custom_prompt = team.get("custom_prompt", "")
    for round_num in range(max_rounds):
        for idx, member in enumerate(members):
            agent_name = member.get("display_name") or member.get("agent_name", f"Agent#{member['agent_id']}")
            role = member.get("role_in_team", "")
            task_rules = member.get("task_rules", "")
            if cb: cb("debate_round", {"round": round_num+1, "agent": agent_name, "role": role})
            previous = ""
            if debate_log: previous = "之前的讨论：\n" + "\n".join(debate_log[-len(members)*2:])
            prompt = f"你是一名{agent_name}。职责：{role}\n"
            prompt += "请给出你对该问题的初步专业分析。" if round_num == 0 else "请基于前面的讨论，补充或反驳其他专家的观点。"
            if task_rules:
                prompt += f"\n\n【自定义任务规则】\n{task_rules}"
            if custom_prompt:
                prompt += f"\n\n【团队自定义指令】\n{custom_prompt}"
            output = call_llm(prompt, context=f"问题：{question}\n\n{previous}", model=model)
            if not output: output = f"（{agent_name}在第{round_num+1}轮保持原观点）"
            _save_step(cur, workflow_id, round_num*len(members)+idx+1, member["agent_id"], agent_name,
                       (question[:300]+"\n"+previous[:300]), output, decision=f"第{round_num+1}轮")
            conn.commit()
            debate_log.append(f"第{round_num+1}轮-{agent_name}：{output[:200]}...")
            if cb: cb("debate_output", {"round": round_num+1, "agent": agent_name, "output": output})
    if cb: cb("summarizing", {"message": "辩论结束，正在汇总裁决..."})
    context = f"问题：{question}\n\n辩论记录：\n" + "\n".join(debate_log)
    final = call_llm(SYSTEM_PROMPTS["debate_moderator"], context=context, model=model)
    return final or (debate_log[-1] if debate_log else question)


def run_team_stream(team_id, question, session_id=""):
    """流式运行团队，逐步 yield SSE 事件。在子线程中运行，通过队列传事件"""
    from services.team_service import get_team

    team = get_team(team_id)
    if not team:
        yield f"data: {json.dumps({'type': 'error', 'error': '团队不存在'})}\n\n"
        return

    main_conn = get_db()
    main_cur = main_conn.cursor()
    main_cur.execute("INSERT INTO cpa_workflow_runs (session_id, team_id, question, status) VALUES (%s, %s, %s, 'running') RETURNING id",
                (session_id, team_id, question))
    workflow_id = main_cur.fetchone()[0]
    main_conn.commit()
    main_cur.close()
    main_conn.close()

    yield f"data: {json.dumps({'type': 'start', 'team_name': team['name'], 'workflow_type': team['workflow_type'], 'member_count': len(team['members'])})}\n\n"

    evt_queue = queue.Queue()

    def cb(stage, data):
        evt_queue.put((stage, data))

    def worker():
        worker_conn = None
        worker_cur = None
        try:
            worker_conn = get_db()
            worker_cur = worker_conn.cursor()
            if team["workflow_type"] == "sequential":
                result = _run_sequential(workflow_id, team, question, worker_cur, worker_conn, cb)
            elif team["workflow_type"] == "parallel":
                result = _run_parallel(workflow_id, team, question, worker_cur, worker_conn, cb)
            elif team["workflow_type"] == "debate":
                result = _run_debate(workflow_id, team, question, worker_cur, worker_conn, cb)
            else:
                result = _run_sequential(workflow_id, team, question, worker_cur, worker_conn, cb)
            worker_cur.execute("UPDATE cpa_workflow_runs SET status='done', final_answer=%s, finished_at=NOW() WHERE id=%s", (result, workflow_id))
            worker_conn.commit()
            evt_queue.put(("_done", {"answer": result}))
        except Exception as e:
            try:
                if worker_cur:
                    worker_cur.execute("UPDATE cpa_workflow_runs SET status='failed', finished_at=NOW() WHERE id=%s", (workflow_id,))
                    worker_conn.commit()
            except:
                pass
            evt_queue.put(("_error", {"error": str(e)}))
        finally:
            try:
                if worker_cur: worker_cur.close()
                if worker_conn: worker_conn.close()
            except:
                pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    try:
        while True:
            try:
                stage, data = evt_queue.get(timeout=1)
                if stage == "_done":
                    yield f"data: {json.dumps({'type': 'done', 'answer': data['answer']})}\n\n"
                    break
                elif stage == "_error":
                    yield f"data: {json.dumps({'type': 'error', 'error': data['error']})}\n\n"
                    break
                elif stage == "agent_start":
                    yield f"data: {json.dumps({'type': 'agent_start', **data})}\n\n"
                elif stage == "agent_output":
                    yield f"data: {json.dumps({'type': 'agent_output', 'agent': data['agent'], 'output': data['output']})}\n\n"
                elif stage == "debate_round":
                    yield f"data: {json.dumps({'type': 'debate_round', **data})}\n\n"
                elif stage == "debate_output":
                    yield f"data: {json.dumps({'type': 'agent_output', 'agent': data['agent'], 'output': data['output'], 'round': data['round']})}\n\n"
                elif stage == "summarizing":
                    yield f"data: {json.dumps({'type': 'summarizing', **data})}\n\n"
            except queue.Empty:
                if not t.is_alive():
                    break
                continue
    except GeneratorExit:
        pass
