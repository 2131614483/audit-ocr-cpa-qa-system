-- ============================================
-- 知识图谱独立数据库
-- 数据库: cpa_knowledge_graph
-- 独立于现有的 cpa_knowledge 数据库
-- ============================================

CREATE DATABASE cpa_knowledge_graph
    WITH ENCODING 'UTF8'
    OWNER postgres;

COMMENT ON DATABASE cpa_knowledge_graph IS 'CPA知识图谱数据库 — 存储实体、关系、公式、易混概念、社区检测结果';
