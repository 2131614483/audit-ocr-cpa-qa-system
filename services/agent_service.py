import psycopg2
import json

DB_CONFIG = {"host": "localhost", "port": 5432, "dbname": "cpa_knowledge", "user": "postgres", "password": "admin"}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def list_agents(search=""):
    conn = get_db()
    cur = conn.cursor()
    if search:
        cur.execute("""
            SELECT id, name, role, display_name, description, model, temperature, skills, icon, is_builtin, created_at
            FROM cpa_agent_configs
            WHERE name ILIKE %s OR display_name ILIKE %s OR description ILIKE %s
            ORDER BY is_builtin DESC, id ASC
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""
            SELECT id, name, role, display_name, description, model, temperature, skills, icon, is_builtin, created_at
            FROM cpa_agent_configs ORDER BY is_builtin DESC, id ASC
        """)
    items = []
    for r in cur.fetchall():
        items.append({
            "id": r[0], "name": r[1], "role": r[2], "display_name": r[3],
            "description": r[4], "model": r[5], "temperature": float(r[6]) if r[6] else 0.3,
            "skills": r[7] or [], "icon": r[8] or "🤖", "is_builtin": r[9],
            "created_at": str(r[10]) if r[10] else ""
        })
    cur.close()
    conn.close()
    return items

def get_agent(agent_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, role, display_name, description, prompt_template, model, temperature,
               max_tokens, style, skills, capabilities, decision_rules, icon, is_builtin, created_at, updated_at
        FROM cpa_agent_configs WHERE id = %s
    """, (agent_id,))
    r = cur.fetchone()
    cur.close()
    conn.close()
    if not r:
        return None
    return {
        "id": r[0], "name": r[1], "role": r[2], "display_name": r[3],
        "description": r[4], "prompt_template": r[5], "model": r[6],
        "temperature": float(r[7]) if r[7] else 0.3,
        "max_tokens": r[8], "style": r[9], "skills": r[10] or [],
        "capabilities": r[11], "decision_rules": r[12], "icon": r[13] or "🤖",
        "is_builtin": r[14], "created_at": str(r[15]) if r[15] else "",
        "updated_at": str(r[16]) if r[16] else ""
    }

def create_agent(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cpa_agent_configs (name, role, display_name, description, prompt_template, model, temperature, max_tokens, style, skills, capabilities, decision_rules, icon)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        data.get("name"), data.get("role"), data.get("display_name"),
        data.get("description"), data.get("prompt_template"),
        data.get("model", "deepseek-chat"), data.get("temperature", 0.3),
        data.get("max_tokens", 2000), data.get("style", "text"),
        data.get("skills", []), data.get("capabilities"),
        data.get("decision_rules"), data.get("icon", "🤖")
    ))
    agent_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return get_agent(agent_id)

def update_agent(agent_id, data):
    conn = get_db()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ["name", "role", "display_name", "description", "prompt_template", "model", "style", "capabilities", "decision_rules", "icon"]:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if "temperature" in data:
        fields.append("temperature = %s")
        values.append(data["temperature"])
    if "max_tokens" in data:
        fields.append("max_tokens = %s")
        values.append(data["max_tokens"])
    if "skills" in data:
        fields.append("skills = %s")
        values.append(data["skills"])
    if fields:
        fields.append("updated_at = NOW()")
        values.append(agent_id)
        cur.execute(f"UPDATE cpa_agent_configs SET {', '.join(fields)} WHERE id = %s", values)
        conn.commit()
    cur.close()
    conn.close()
    return get_agent(agent_id)

def delete_agent(agent_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cpa_agent_configs WHERE id = %s AND is_builtin = FALSE", (agent_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted
