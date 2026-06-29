-- Chainlit Database Initialization Script
-- For SQLite with SQLAlchemyDataLayer

-- Users table (createdAt without NOT NULL constraint)
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT UNIQUE NOT NULL,
    "createdAt" TEXT,
    "metadata" TEXT
);

-- Threads table (createdAt without NOT NULL constraint)
CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "metadata" TEXT
);

-- Steps table
CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "threadId" TEXT,
    "parentId" TEXT,
    "disableFeedback" INTEGER,
    "streaming" INTEGER,
    "waitForAnswer" INTEGER,
    "isError" INTEGER,
    "metadata" TEXT,
    "tags" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" TEXT,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INTEGER,
    "defaultOpen" INTEGER
);

-- Feedbacks table
CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT,
    "threadId" TEXT,
    "value" REAL,
    "comment" TEXT,
    "createdAt" TEXT
);

-- Elements table
CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "forId" TEXT,
    "type" TEXT,
    "url" TEXT,
    "name" TEXT,
    "display" TEXT,
    "objectKey" TEXT,
    "chainlitKey" TEXT,
    "size" INTEGER,
    "page" INTEGER,
    "language" TEXT,
    "mime" TEXT,
    "props" TEXT,
    "createdAt" TEXT
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_threads_userId ON threads("userId");
CREATE INDEX IF NOT EXISTS idx_threads_userIdentifier ON threads("userIdentifier");
CREATE INDEX IF NOT EXISTS idx_steps_threadId ON steps("threadId");
CREATE INDEX IF NOT EXISTS idx_feedbacks_forId ON feedbacks("forId");
CREATE INDEX IF NOT EXISTS idx_feedbacks_threadId ON feedbacks("threadId");
CREATE INDEX IF NOT EXISTS idx_elements_threadId ON elements("threadId");
CREATE INDEX IF NOT EXISTS idx_elements_forId ON elements("forId");

-- ==================== 每日一练系统表 ====================

-- 练习记录表（存储每次练习的总览信息）
CREATE TABLE IF NOT EXISTS practice_records (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    "correct_count" INTEGER NOT NULL DEFAULT 0,
    "wrong_count" INTEGER NOT NULL DEFAULT 0,
    "current_streak" INTEGER NOT NULL DEFAULT 0,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 错题本表（存储每次练习中的错题明细）
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

-- 用户排行榜表（存储每个用户的累计成绩，用于排名计算）
CREATE TABLE IF NOT EXISTS user_leaderboard (
    "username" TEXT PRIMARY KEY,
    "total_score" INTEGER NOT NULL DEFAULT 0,
    "highest_score" INTEGER NOT NULL DEFAULT 0,
    "practice_count" INTEGER NOT NULL DEFAULT 0,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 练习记录索引
CREATE INDEX IF NOT EXISTS idx_practice_records_username ON practice_records("username");
CREATE INDEX IF NOT EXISTS idx_practice_records_created_at ON practice_records("created_at");

-- 错题本索引
CREATE INDEX IF NOT EXISTS idx_mistake_details_record_id ON mistake_details("record_id");
CREATE INDEX IF NOT EXISTS idx_mistake_details_username ON mistake_details("username");

-- 排行榜索引（按总分降序排名用）
CREATE INDEX IF NOT EXISTS idx_user_leaderboard_total_score ON user_leaderboard("total_score");

-- ==================== 作业系统表 ====================

-- 作业成绩记录表（存储每次作业的成绩和反馈）
CREATE TABLE IF NOT EXISTS assignment_records (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    "feedback" TEXT NOT NULL DEFAULT '',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 作业记录索引
CREATE INDEX IF NOT EXISTS idx_assignment_records_username ON assignment_records("username");
CREATE INDEX IF NOT EXISTS idx_assignment_records_created_at ON assignment_records("created_at");
