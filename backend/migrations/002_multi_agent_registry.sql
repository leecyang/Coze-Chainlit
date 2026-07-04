-- Dynamic multi-agent registry and routing tables.

CREATE TABLE IF NOT EXISTS agent_definitions (
    "agent_id" TEXT PRIMARY KEY,
    "display_name" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "agent_type" TEXT NOT NULL DEFAULT 'coze_chat',
    "bot_id" TEXT NOT NULL DEFAULT '',
    "enabled" INTEGER NOT NULL DEFAULT 1,
    "system_builtin" INTEGER NOT NULL DEFAULT 0,
    "locked" INTEGER NOT NULL DEFAULT 0,
    "exclusive" INTEGER NOT NULL DEFAULT 0,
    "priority" INTEGER NOT NULL DEFAULT 100,
    "context_policy" TEXT NOT NULL DEFAULT 'on_switch_recent_2',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK ("agent_type" IN ('coze_chat', 'coze_workflow')),
    CHECK ("context_policy" IN ('on_switch_recent_2', 'none'))
);

CREATE TABLE IF NOT EXISTS agent_subscriptions (
    "agent_id" TEXT NOT NULL,
    "topic" TEXT NOT NULL,
    "base_bid" REAL NOT NULL DEFAULT 0,
    "basic_bonus" REAL NOT NULL DEFAULT 0,
    "advanced_bonus" REAL NOT NULL DEFAULT 0,
    PRIMARY KEY ("agent_id", "topic"),
    FOREIGN KEY ("agent_id") REFERENCES agent_definitions("agent_id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS route_topics (
    "topic" TEXT PRIMARY KEY,
    "display_name" TEXT NOT NULL,
    "description" TEXT NOT NULL DEFAULT '',
    "is_teaching" INTEGER NOT NULL DEFAULT 1,
    "is_exclusive" INTEGER NOT NULL DEFAULT 0,
    "route_priority" INTEGER NOT NULL DEFAULT 100,
    "enabled" INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS route_keywords (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "scope" TEXT NOT NULL,
    "topic" TEXT,
    "kind" TEXT NOT NULL,
    "keyword" TEXT NOT NULL,
    "enabled" INTEGER NOT NULL DEFAULT 1,
    "priority" INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS route_settings (
    "key" TEXT PRIMARY KEY,
    "value" TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_route_keywords_unique
ON route_keywords("scope", COALESCE("topic", ''), "kind", "keyword");

CREATE INDEX IF NOT EXISTS idx_agent_definitions_enabled
ON agent_definitions("enabled");

CREATE INDEX IF NOT EXISTS idx_agent_subscriptions_topic
ON agent_subscriptions("topic");

CREATE INDEX IF NOT EXISTS idx_route_topics_enabled
ON route_topics("enabled");

CREATE INDEX IF NOT EXISTS idx_route_keywords_lookup
ON route_keywords("scope", "topic", "kind", "enabled");

CREATE TRIGGER IF NOT EXISTS trg_agent_definitions_updated_at
AFTER UPDATE ON agent_definitions
FOR EACH ROW
BEGIN
    UPDATE agent_definitions
    SET updated_at = datetime('now', 'localtime')
    WHERE agent_id = OLD.agent_id;
END;
