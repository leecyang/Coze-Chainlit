-- Baseline Chainlit + LingXi runtime schema.

CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT,
    "createdAt" TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "metadata" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "createdAt" TEXT,
    FOREIGN KEY ("userId") REFERENCES users("id")
);

CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "metadata" TEXT,
    "parentId" TEXT,
    "threadId" TEXT,
    "userId" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "startTime" TEXT,
    "endTime" TEXT,
    "defaultOpen" INTEGER,
    "start" TEXT,
    "end" TEXT,
    "streaming" INTEGER,
    "isError" INTEGER,
    "waitForAnswer" INTEGER,
    "showInput" TEXT,
    "generation" TEXT,
    "tags" TEXT,
    "language" TEXT,
    "autoCollapse" INTEGER,
    FOREIGN KEY ("threadId") REFERENCES threads("id"),
    FOREIGN KEY ("userId") REFERENCES users("id")
);

CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "type" TEXT,
    "name" TEXT,
    "metadata" TEXT,
    "threadId" TEXT,
    "url" TEXT,
    "objectKey" TEXT,
    "createdAt" TEXT,
    "chainlitKey" TEXT,
    "display" TEXT,
    "size" INTEGER,
    "language" TEXT,
    "page" INTEGER,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id")
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "value" INTEGER,
    "comment" TEXT,
    "stepId" TEXT,
    "forId" TEXT,
    "threadId" TEXT,
    "createdAt" TEXT,
    FOREIGN KEY ("stepId") REFERENCES steps("id")
);

CREATE TABLE IF NOT EXISTS attachments (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "metadata" TEXT,
    "threadId" TEXT,
    "stepId" TEXT,
    "objectKey" TEXT,
    "createdAt" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id"),
    FOREIGN KEY ("stepId") REFERENCES steps("id")
);

CREATE TABLE IF NOT EXISTS practice_records (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    "correct_count" INTEGER NOT NULL DEFAULT 0,
    "wrong_count" INTEGER NOT NULL DEFAULT 0,
    "current_streak" INTEGER NOT NULL DEFAULT 0,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS mistake_details (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "record_id" INTEGER NOT NULL,
    "username" TEXT NOT NULL,
    "question_id" TEXT NOT NULL,
    "question_text" TEXT NOT NULL DEFAULT '',
    "user_answer" TEXT NOT NULL DEFAULT '',
    "correct_answer" TEXT NOT NULL DEFAULT '',
    "analysis" TEXT NOT NULL DEFAULT '',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY ("record_id") REFERENCES practice_records("id")
);

CREATE TABLE IF NOT EXISTS user_leaderboard (
    "username" TEXT PRIMARY KEY,
    "total_score" INTEGER NOT NULL DEFAULT 0,
    "highest_score" INTEGER NOT NULL DEFAULT 0,
    "practice_count" INTEGER NOT NULL DEFAULT 0,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS app_users (
    "username" TEXT PRIMARY KEY,
    "password" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'user',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS app_activity_logs (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "actor" TEXT,
    "target" TEXT,
    "detail" TEXT,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS assignment_records (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    "feedback" TEXT NOT NULL DEFAULT '',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS app_config (
    "key" TEXT PRIMARY KEY,
    "value" TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conversation_user_mapping (
    "conversation_id" TEXT PRIMARY KEY,
    "username" TEXT NOT NULL,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS persona_usage_logs (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "persona" TEXT NOT NULL,
    "thread_id" TEXT,
    "created_at" TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_practice_records_username ON practice_records("username");
CREATE INDEX IF NOT EXISTS idx_practice_records_created_at ON practice_records("created_at");
CREATE INDEX IF NOT EXISTS idx_mistake_details_record_id ON mistake_details("record_id");
CREATE INDEX IF NOT EXISTS idx_mistake_details_username ON mistake_details("username");
CREATE INDEX IF NOT EXISTS idx_user_leaderboard_total_score ON user_leaderboard("total_score");
CREATE INDEX IF NOT EXISTS idx_assignment_records_username ON assignment_records("username");
CREATE INDEX IF NOT EXISTS idx_assignment_records_created_at ON assignment_records("created_at");
CREATE INDEX IF NOT EXISTS idx_app_activity_logs_actor ON app_activity_logs("actor");
CREATE INDEX IF NOT EXISTS idx_app_activity_logs_target ON app_activity_logs("target");
