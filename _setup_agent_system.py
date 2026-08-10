import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='cpa_knowledge', user='postgres', password='admin')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS cpa_agent_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    prompt_template TEXT NOT NULL,
    model VARCHAR(100) DEFAULT 'deepseek-chat',
    temperature FLOAT DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 2000,
    style VARCHAR(50) DEFAULT 'text',
    skills TEXT[],
    capabilities TEXT,
    decision_rules TEXT,
    icon VARCHAR(20) DEFAULT '🤖',
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS cpa_team_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    workflow_type VARCHAR(30) NOT NULL,
    max_rounds INTEGER DEFAULT 3,
    decision_mode VARCHAR(30) DEFAULT 'consensus',
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS cpa_team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES cpa_team_configs(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES cpa_agent_configs(id) ON DELETE CASCADE,
    role_in_team VARCHAR(100),
    task_rules TEXT,
    priority INTEGER DEFAULT 0,
    input_from TEXT[],
    output_to TEXT[]
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS cpa_workflow_runs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    team_id INTEGER REFERENCES cpa_team_configs(id),
    question TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'running',
    final_answer TEXT,
    total_cost FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS cpa_workflow_steps (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES cpa_workflow_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    agent_id INTEGER REFERENCES cpa_agent_configs(id),
    agent_name VARCHAR(100),
    input_text TEXT,
    output_text TEXT,
    token_used INTEGER DEFAULT 0,
    duration_sec FLOAT,
    decision TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
print("✅ 表创建完成")

# 插入内置 Agent
cur.execute("SELECT COUNT(*) FROM cpa_agent_configs")
if cur.fetchone()[0] == 0:
    agents = [
        ('会计专家', 'accounting', '会计专家', '专业会计知识解答',
         '你是一名专业的注册会计师考试辅导专家，请根据提供的知识库内容回答问题。回答要准确、详细，并引用相关知识点。',
         'deepseek-chat', 0.3, ['knowledge_search', 'qa_history_search'], '📊', True),
        ('审计专家', 'auditing', '审计专家', '精通审计准则和实务操作',
         '你是一名专业的审计师，精通审计准则和实务操作。请根据知识库内容提供专业的审计相关回答。',
         'deepseek-chat', 0.3, ['knowledge_search', 'qa_history_search'], '🔍', True),
        ('税法专家', 'tax', '税法专家', '熟悉中国税法法规',
         '你是一名税务专家，熟悉中国税法法规。请提供准确的税务咨询和法规解释。',
         'deepseek-chat', 0.3, ['knowledge_search', 'qa_history_search'], '💰', True),
        ('综合顾问', 'general', '综合顾问', '综合性 CPA 考试辅导',
         '你是一名综合性的CPA考试辅导专家，擅长解答各类会计、审计、税法、财务管理等问题。',
         'deepseek-chat', 0.3, ['knowledge_search', 'qa_history_search', 'calculator'], '🎯', True),
    ]
    for a in agents:
        cur.execute("""
            INSERT INTO cpa_agent_configs (name, role, display_name, description, prompt_template, model, temperature, skills, icon, is_builtin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, a)
    conn.commit()
    print("✅ 内置 Agent 已插入")

cur.execute("SELECT COUNT(*) FROM cpa_team_configs")
if cur.fetchone()[0] == 0:
    teams = [
        ('完整审计工作流', '从审计风险识别到报告输出的完整审计分析流程', 'sequential', 3, 'consensus', True),
        ('多角度分析', '多个专家同时分析同一问题，汇总不同角度观点', 'parallel', 3, 'consensus', True),
        ('辩论式审查', '会计与审计专家辩论，综合顾问裁决', 'debate', 3, 'consensus', True),
    ]
    for t in teams:
        cur.execute("""
            INSERT INTO cpa_team_configs (name, description, workflow_type, max_rounds, decision_mode, is_builtin)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, t)
    conn.commit()
    print("✅ 内置团队已插入")

print("\n📋 验证:")
for tbl in ['cpa_agent_configs', 'cpa_team_configs', 'cpa_team_members', 'cpa_workflow_runs', 'cpa_workflow_steps']:
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    print(f"  {tbl}: {cur.fetchone()[0]} 条")

cur.close()
conn.close()
