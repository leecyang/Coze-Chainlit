#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建 Chainlit 所需的 SQLite 数据库表
"""

import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# 数据库路径
# Docker 环境：/app/data/chainlit.db (映射到宿主机 ./data)
# 本地开发：data/chainlit.db 或回退到 chainlit.db
if os.path.exists("/app/data"):
    # Docker 环境
    DB_PATH = "/app/data/chainlit.db"
elif os.path.exists("data"):
    # 本地开发，使用 data 目录
    DB_PATH = "data/chainlit.db"
else:
    # 回退到当前目录
    DB_PATH = "chainlit.db"

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# 创建表的 SQL 语句
CREATE_TABLES_SQL = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT,
    "createdAt" TEXT
);

-- 线程表
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

-- 步骤表（包含所有 Chainlit 所需字段）
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

-- 元素表（包含所有 Chainlit 所需字段）
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

-- 反馈表（包含所有 Chainlit 所需字段）
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

-- 附件表
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

-- ==================== 每日一练系统表 ====================

-- 练习记录表
CREATE TABLE IF NOT EXISTS practice_records (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    "correct_count" INTEGER NOT NULL DEFAULT 0,
    "wrong_count" INTEGER NOT NULL DEFAULT 0,
    "current_streak" INTEGER NOT NULL DEFAULT 0,
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 错题本表
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

-- 用户排行榜表
CREATE TABLE IF NOT EXISTS user_leaderboard (
    "username" TEXT PRIMARY KEY,
    "total_score" INTEGER NOT NULL DEFAULT 0,
    "highest_score" INTEGER NOT NULL DEFAULT 0,
    "practice_count" INTEGER NOT NULL DEFAULT 0,
    "updated_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 应用用户表（持久化用户凭证，解决容器重启后用户丢失问题）
CREATE TABLE IF NOT EXISTS app_users (
    "username" TEXT PRIMARY KEY,
    "password" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'user',
    "created_at" TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 练习系统索引
CREATE INDEX IF NOT EXISTS idx_practice_records_username ON practice_records("username");
CREATE INDEX IF NOT EXISTS idx_mistake_details_record_id ON mistake_details("record_id");
CREATE INDEX IF NOT EXISTS idx_mistake_details_username ON mistake_details("username");
CREATE INDEX IF NOT EXISTS idx_user_leaderboard_total_score ON user_leaderboard("total_score");
"""

async def migrate_database(engine):
    """迁移数据库，添加缺失的字段"""
    print("开始检查数据库迁移...")
    
    # 检查 steps 表是否存在 autoCollapse 字段
    async with engine.begin() as conn:
        try:
            # SQLAlchemy way to check if column exists
            result = await conn.execute(text("PRAGMA table_info(steps)"))
            columns = [row[1] for row in result.fetchall()]
            
            if columns and "autoCollapse" not in columns:
                print("发现 steps 表缺少 autoCollapse 字段，正在添加...")
                await conn.execute(text('ALTER TABLE steps ADD COLUMN "autoCollapse" INTEGER'))
                print("autoCollapse 字段添加成功")
            else:
                print("steps 表结构已是最新")
                
        except Exception as e:
            print(f"迁移检查中出错 (可能表尚未创建): {e}")

async def init_database():
    """初始化数据库
    
    注意：修改后支持增量更新。
    现有数据库会被检查并添加缺失字段，历史数据会被保留。
    """
    print(f"正在初始化数据库: {DB_PATH}")
    
    # 确保数据目录存在
    data_dir = os.path.dirname(DB_PATH)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"创建数据目录: {data_dir}")
    
    # 创建引擎
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # 执行创建表的 SQL
        for statement in CREATE_TABLES_SQL.split(';'):
            statement = statement.strip()
            if statement:
                try:
                    await conn.execute(text(statement))
                    # print(f"执行 SQL: {statement[:50]}...")
                except Exception as e:
                    # 如果表已存在会报错，这里忽略
                    pass
    
    # 执行迁移 logic
    await migrate_database(engine)
    
    await engine.dispose()
    print("数据库维护完成！")

if __name__ == "__main__":
    asyncio.run(init_database())
