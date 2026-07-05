# 协作指南

本文档说明 LingXi Chat 的分支定位、开发基线和 Pull Request 提交流程。新开发者在开始贡献前，应先阅读本文件和 README。

## 分支定位

- `main`：当前主要开发和维护的全栈版本，fork 自 `release/v2-refactor-candidate`，包含 React/Vite 前端和 Python Chainlit/FastAPI 后端。除非维护者另有说明，所有常规功能、修复和部署改动都应以该分支为基线。
- `release/v2-refactor-candidate`：`main` 的上游重构候选基线，主要用于记录 v2 全栈重构来源。
- `v1-legacy-stable`：已弃用的纯后端版本，仅作为历史稳定版本保留，不再作为新功能开发基线。
- `dev/v3-upgrade-beta`：基于 `main` 扩展的多智能体版本，目前处于 beta 阶段，不保证可用性和接口稳定性。只有与 v3 多智能体能力直接相关的改动才应提交到该分支。

## 开发基线

日常协作默认从 `main` 创建功能分支。除非任务明确要求维护旧版本或 beta 版本，不要从 `v1-legacy-stable` 或 `dev/v3-upgrade-beta` 开始开发。

建议分支命名：

```bash
feature/short-description
fix/short-description
docs/short-description
chore/short-description
```

## Fork 与本地开发流程

1. 在代码托管平台上 fork 本仓库到自己的账号或组织。
2. 克隆自己的 fork：

```bash
git clone <your-fork-url>
cd Chainlit
```

3. 添加上游仓库地址：

```bash
git remote add upstream <upstream-repo-url>
git remote -v
```

4. 同步 `main` 分支：

```bash
git fetch upstream
git checkout main
git pull --ff-only upstream main
git push origin main
```

5. 从最新 `main` 创建开发分支：

```bash
git checkout -b feature/short-description
```

6. 完成开发后，在本地运行必要的检查。至少确认相关后端、前端或 Docker 启动路径没有被破坏。

7. 提交改动：

```bash
git status
git add <changed-files>
git commit -m "type(scope): concise description"
```

8. 推送到自己的 fork：

```bash
git push -u origin feature/short-description
```

9. 在代码托管平台发起 Pull Request，目标分支选择上游仓库的 `main`。

## Pull Request 规范

- PR 目标分支默认选择 `main`。只有维护者明确要求时，才提交到 `dev/v3-upgrade-beta` 或其他分支。
- 一个 PR 只解决一个明确问题，避免混合无关重构、格式化和功能改动。
- PR 标题建议使用 `type(scope): description`，例如 `fix(auth): handle expired admin session` 或 `docs(readme): localize setup guide`。
- PR 描述应包含改动目的、主要实现、验证方式和可能影响范围。
- 如果改动涉及界面、接口、部署配置或数据库结构，应在 PR 中明确说明。
- 不要提交密钥、`.env`、数据库文件、虚拟环境、`node_modules`、构建产物或本地调试文件。
- 提交前先同步上游 `main`，解决冲突后再请求 review。

## 提交前检查

根据改动范围选择运行：

```bash
# 后端依赖与数据库初始化
cd backend
python init_db.py

# 后端本地启动
python -m chainlit run app.py --host 0.0.0.0 --port 8000

# 前端依赖与开发服务
cd frontend
pnpm install
pnpm dev --host 0.0.0.0 --port 5173

# Docker 部署路径
docker compose up --build -d
docker compose logs -f lingxi-backend
```

如果某些检查无法运行，请在 PR 描述中说明原因和已完成的替代验证。
