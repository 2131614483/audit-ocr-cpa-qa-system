import psycopg2
import json

DB_CONFIG = {"host": "localhost", "port": 5432, "dbname": "cpa_knowledge", "user": "postgres", "password": "admin"}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def list_teams(search=""):
    conn = get_db()
    cur = conn.cursor()
    if search:
        cur.execute("""
            SELECT id, name, description, workflow_type, max_rounds, decision_mode, is_builtin, created_at, custom_prompt, model_override
            FROM cpa_team_configs
            WHERE name ILIKE %s OR description ILIKE %s
            ORDER BY is_builtin DESC, id ASC
        """, (f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""
            SELECT id, name, description, workflow_type, max_rounds, decision_mode, is_builtin, created_at, custom_prompt, model_override
            FROM cpa_team_configs ORDER BY is_builtin DESC, id ASC
        """)
    items = []
    for r in cur.fetchall():
        items.append({
            "id": r[0], "name": r[1], "description": r[2],
            "workflow_type": r[3], "max_rounds": r[4],
            "decision_mode": r[5], "is_builtin": r[6],
            "created_at": str(r[7]) if r[7] else "",
            "custom_prompt": r[8], "model_override": r[9]
        })
    cur.close()
    conn.close()
    return items

def get_team(team_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, workflow_type, max_rounds, decision_mode, is_builtin, created_at, custom_prompt, model_override
        FROM cpa_team_configs WHERE id = %s
    """, (team_id,))
    r = cur.fetchone()
    if not r:
        cur.close()
        conn.close()
        return None
    team = {
        "id": r[0], "name": r[1], "description": r[2], "workflow_type": r[3],
        "max_rounds": r[4], "decision_mode": r[5], "is_builtin": r[6],
        "created_at": str(r[7]) if r[7] else "", "members": [],
        "custom_prompt": r[8], "model_override": r[9]
    }
    cur.execute("""
        SELECT m.id, m.agent_id, a.name, a.display_name, a.icon, m.role_in_team, m.task_rules, m.priority
        FROM cpa_team_members m
        JOIN cpa_agent_configs a ON m.agent_id = a.id
        WHERE m.team_id = %s ORDER BY m.priority ASC
    """, (team_id,))
    for m in cur.fetchall():
        team["members"].append({
            "id": m[0], "agent_id": m[1], "agent_name": m[2],
            "display_name": m[3], "icon": m[4] or "🤖",
            "role_in_team": m[5], "task_rules": m[6], "priority": m[7]
        })
    cur.close()
    conn.close()
    return team

def create_team(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cpa_team_configs (name, description, workflow_type, max_rounds, decision_mode, custom_prompt, model_override)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (data.get("name"), data.get("description"), data.get("workflow_type", "sequential"),
          data.get("max_rounds", 3), data.get("decision_mode", "consensus"),
          data.get("custom_prompt"), data.get("model_override")))
    team_id = cur.fetchone()[0]
    # 添加成员
    for i, member in enumerate(data.get("members", [])):
        cur.execute("""
            INSERT INTO cpa_team_members (team_id, agent_id, role_in_team, task_rules, priority)
            VALUES (%s, %s, %s, %s, %s)
        """, (team_id, member.get("agent_id"), member.get("role_in_team", ""),
              member.get("task_rules"), i))
    conn.commit()
    cur.close()
    conn.close()
    return get_team(team_id)

def update_team(team_id, data):
    conn = get_db()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ["name", "description", "workflow_type", "decision_mode", "custom_prompt", "model_override"]:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if "max_rounds" in data:
        fields.append("max_rounds = %s")
        values.append(data["max_rounds"])
    if fields:
        values.append(team_id)
        cur.execute(f"UPDATE cpa_team_configs SET {', '.join(fields)} WHERE id = %s", values)

    if "members" in data:
        cur.execute("DELETE FROM cpa_team_members WHERE team_id = %s", (team_id,))
        for i, member in enumerate(data["members"]):
            cur.execute("""
                INSERT INTO cpa_team_members (team_id, agent_id, role_in_team, task_rules, priority)
                VALUES (%s, %s, %s, %s, %s)
            """, (team_id, member.get("agent_id"), member.get("role_in_team", ""),
                  member.get("task_rules"), i))
    conn.commit()
    cur.close()
    conn.close()
    return get_team(team_id)

def delete_team(team_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cpa_team_configs WHERE id = %s AND is_builtin = FALSE", (team_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted
