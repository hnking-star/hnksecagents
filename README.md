# hnksecagents

`hnksecagents` 是对 `open-ptc-agent` 的一版本地化重构。

当前目标不是完整复刻原项目，而是先保住一条能工作的主链路：
- 去掉 Daytona，改成本地运行
- 去掉 MCP
- 保留 `task / wait / task_output` 多 agent 协作模式
- 继续使用 PTC 风格的 agent 组织方式
- 支持用 `langgraph dev` 直接观察图和中间件

## 当前状态

当前项目已经具备这些能力：
- 本地 Python 与 Shell 执行
- 文件读写、`glob`、`grep`
- 后台子代理编排
- `task / wait / task_output` 工作流
- `langgraph dev` 开发入口
- 使用 `deepagents` 自带 `SkillsMiddleware`

当前还没有做的事：
- 不再使用 Daytona
- 不再使用 MCP
- CLI 结构暂未重构
- 更完整的 prompt loader / 模板体系还可以继续细化

## 技术栈

- Python 3.12
- `langchain`
- `langgraph`
- `deepagents`
- `langchain-openai`
- `langgraph-cli[inmem]`

## 目录结构

```text
hnksecagents/
├── hnk_agent/
│   ├── agent/                # 主 agent 装配、middleware、subagent、tools
│   ├── config/               # 配置模型与加载器
│   ├── llm/                  # LLM 工厂
│   ├── runtime/              # 本地运行时与工作区
│   ├── session/              # 会话初始化与装配入口
│   └── tooling/              # 内建工具注册与模块构建
├── skills/                   # 项目级 skills
├── tools/                    # execute_code 生成的本地工具模块目录
├── results/                  # 输出结果目录
├── examples/                 # 示例文件
├── langgraph.json            # langgraph dev 入口配置
├── .env.example              # 环境变量示例
└── pyproject.toml
```

## 安装

如果你要从零开始：

```bash
cd hnksecagents
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

如果你已经有 `.venv`，只需要：

```bash
cd hnksecagents
source .venv/bin/activate
```

## 环境变量

项目通过 `.env` 读取模型配置。先从示例复制一份：

```bash
cp .env.example .env
```

最小示例可参考：

```env
HNKSECAGENTS_MODEL=gpt-4o-mini
HNKSECAGENTS_MODEL_PROVIDER=openai
# HNKSECAGENTS_API_KEY=
# HNKSECAGENTS_BASE_URL=
# HNKSECAGENTS_TEMPERATURE=0
# HNKSECAGENTS_MAX_TOKENS=4096
# HNKSECAGENTS_WORKSPACE_ROOT=/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents
```

默认会读取项目根目录下的 `.env`。

## 运行

### 启动 langgraph dev

```bash
.venv/bin/langgraph dev --allow-blocking --no-browser
```

当前图入口在：
- [langgraph_entry.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/agent/langgraph_entry.py)
- [langgraph.json](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/langgraph.json)

如果你改了 `langgraph_entry.py`、skills 目录、或 middleware 装配，记得重启 `langgraph dev`，不要只刷新页面。

## Skills

当前项目已经切到 `deepagents` 自带的 `SkillsMiddleware`。

项目级 skills 目录是：

```text
skills/<skill-name>/SKILL.md
```

用户级 skills 目录是：

```text
~/.hnksecagents/skills/<skill-name>/SKILL.md
```

最小 skill 结构示例：

```md
---
name: demo-skill
description: 一个最小可用的示例技能
---

# Demo Skill

这里写完整技能说明。
```

注意：
- `SKILL.md` 必须放在独立目录里
- 顶部必须有 YAML frontmatter
- 至少要有 `name` 和 `description`
- `name` 最好和目录名一致

## 核心入口

如果你想追主调用链，优先看这些文件：

- [agent.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/agent/agent.py)
- [deepagent_middleware.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/agent/middleware/deepagent_middleware.py)
- [langgraph_entry.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/agent/langgraph_entry.py)
- [session.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/session/session.py)
- [local_runtime.py](/Users/bytedance/Desktop/AI_hacker/tencent/hnksecagents/hnk_agent/runtime/local_runtime.py)

## 当前行为说明

主 agent 默认会装配这些能力：
- `execute_code`
- `execute_bash`
- 文件工具
- 后台任务中间件
- `deepagents` 文件系统中间件
- `deepagents` skills 中间件
- 子代理中间件

其中 skills 不再由项目自己拼接到 system prompt，而是交给 `deepagents` 动态注入。

## 后续建议

如果你准备继续往 `ptc-agent` 靠，可以优先做这些事：
- 补更完整的 prompt loader / template 体系
- 扩展更多子代理类型
- 完善配置文件和默认值
- 补测试覆盖 agent 装配和 skills 加载链路
- 再决定是否补 CLI 层
