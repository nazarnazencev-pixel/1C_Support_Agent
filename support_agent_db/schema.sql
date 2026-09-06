PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    department TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'operator', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'cli' CHECK (channel IN ('cli', 'bitrix24', 'redmine', 'web', 'api', 'other')),
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER,
    user_id INTEGER NOT NULL,
    channel TEXT NOT NULL DEFAULT 'cli' CHECK (channel IN ('cli', 'bitrix24', 'redmine', 'web', 'api', 'other')),
    category TEXT,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'success', 'failed', 'escalated')),
    answer TEXT,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    response_time_ms INTEGER CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    was_escalated INTEGER NOT NULL DEFAULT 0 CHECK (was_escalated IN (0,1)),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    request_id INTEGER,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'agent', 'operator', 'system')),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    operator_id INTEGER,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    resolution TEXT,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (operator_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL UNIQUE,
    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT,
    file_path TEXT,
    gigachat_file_id TEXT,
    ocr_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('file', 'url', 'ticket', 'skill', 'manual', 'other')),
    source_url TEXT,
    file_path TEXT,
    version TEXT,
    content_hash TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'processing', 'archived', 'error')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    vector_id TEXT,
    token_count INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    category TEXT,
    source_repo TEXT,
    source_url TEXT,
    skill_type TEXT NOT NULL DEFAULT 'reference' CHECK (skill_type IN ('reference', 'tool', 'workflow', 'router')),
    execution_mode TEXT NOT NULL DEFAULT 'external' CHECK (execution_mode IN ('external', 'local', 'internal')),
    local_path TEXT,
    version TEXT,
    content_hash TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS request_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    document_id INTEGER,
    chunk_id INTEGER,
    skill_id INTEGER,
    relevance_score REAL CHECK (relevance_score IS NULL OR (relevance_score >= 0.0 AND relevance_score <= 1.0)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES knowledge_documents(id) ON DELETE SET NULL,
    FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agent_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_category ON requests(category);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document_id ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_active ON skills(is_active);

CREATE VIEW IF NOT EXISTS v_dashboard_summary AS
SELECT
    COUNT(*) AS total_requests,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_requests,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_requests,
    SUM(CASE WHEN was_escalated = 1 OR status = 'escalated' THEN 1 ELSE 0 END) AS escalated_requests,
    ROUND(AVG(CASE WHEN response_time_ms IS NOT NULL THEN response_time_ms END), 2) AS avg_response_time_ms,
    ROUND(AVG(CASE WHEN confidence IS NOT NULL THEN confidence END), 4) AS avg_confidence,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS success_rate_percent
FROM requests;

CREATE VIEW IF NOT EXISTS v_daily_stats AS
SELECT
    substr(created_at, 1, 10) AS day,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_requests,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_requests,
    SUM(CASE WHEN was_escalated = 1 OR status = 'escalated' THEN 1 ELSE 0 END) AS escalated_requests,
    ROUND(AVG(response_time_ms), 2) AS avg_response_time_ms,
    ROUND(AVG(confidence), 4) AS avg_confidence
FROM requests
GROUP BY substr(created_at, 1, 10)
ORDER BY day DESC;

CREATE VIEW IF NOT EXISTS v_category_stats AS
SELECT
    COALESCE(category, 'Без категории') AS category,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_requests,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_requests,
    SUM(CASE WHEN was_escalated = 1 OR status = 'escalated' THEN 1 ELSE 0 END) AS escalated_requests,
    ROUND(AVG(response_time_ms), 2) AS avg_response_time_ms,
    ROUND(AVG(confidence), 4) AS avg_confidence
FROM requests
GROUP BY category
ORDER BY total_requests DESC;

INSERT OR IGNORE INTO agent_settings(key, value, description) VALUES
('confidence_threshold', '0.80', 'Порог уверенности AI. Ниже этого значения запрос рекомендуется эскалировать оператору.'),
('max_knowledge_results', '3', 'Количество результатов поиска по базе знаний, передаваемых агенту.'),
('target_response_time_ms', '5000', 'Целевое время генерации ответа по требованиям проекта.'),
('knowledge_search_mode', 'local', 'Режим поиска: local сейчас, vector после подключения векторной БД.');
