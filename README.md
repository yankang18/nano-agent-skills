# SkillPD

**Skill Progressive Disclosure** - 渐进披露架构的 AI Agent 框架，通过三级加载机制降低大模型上下文 Token 消耗。也能使Agent能够集中注意力做正确的事。

## 核心概念

渐进披露（Progressive Disclosure）将 Skill 信息分为三级按需加载：

| Level | 内容 | 加载时机 | 典型大小 |
|-------|------|----------|----------|
| **Level 1** | Skill 元数据（名称、描述） | 启动时常驻 | ~100 tokens |
| **Level 2** | SKILL.md 完整指令 | 意图匹配时加载 | ~1000+ tokens |
| **Level 3** | 引用文件（规范、脚本等） | 执行时按需读取 | 视文件大小 |

相比全量加载，可节省 **80%+** 的上下文开销。

## 项目结构

```
SkillPD/
├── agent.py              # 完整 Agent（真实 LLM 交互）
├── agent_mock.py         # Mock Agent（演示用，无需 API Key）
├── skills.py             # Skill 注册表，管理三级加载
├── tools.py              # 工具实现：SkillTool / ReadFileTool / BashTool
├── llms.py               # LLM 客户端（OpenAI 兼容 API）
├── prompts.py            # 系统提示词模板
├── skill_env.py          # 演示环境初始化
├── .env                  # API 配置（仅 agent.py 需要）
└── .claude/skills/       # Skill 目录
    └── code-reviewer/
        ├── SKILL.md              # Skill 定义与工作流程
        ├── references/           # Level 3 资源
        │   └── style-guide.md
        └── scripts/              # Level 3 资源
            └── lint.sh
```

## 核心模块

| 文件 | 职责 |
|------|------|
| `skills.py` | `SkillRegistry` - 扫描 Skill 目录，管理元数据缓存和三级加载 |
| `tools.py` | `Tool` 基类；`SkillTool` 触发 Level 2；`ReadFileTool` 支持 Level 3 相对路径解析 |
| `llms.py` | `LLMClient` - 封装 OpenAI 兼容 API 调用 |
| `agent.py` | `AgentLoop` - 主循环，处理用户输入、模型推理、工具调用 |
| `agent_mock.py` | `MockAgent` - 模拟模型输出，用于演示 |


## 启动方式

### 方式一：Mock 演示（无需 API Key）

适合理解渐进披露机制：

```bash
python agent_mock.py
```

输出展示完整的三级披露流程。

### 方式二：真实 LLM 交互

需要配置 API Key：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env：OPENAI_API_KEY=xxx, BASE_URL=xxx, MODEL_ID=xxx

# 2. 运行
python agent.py
```

启动后进入交互式会话，输入 `帮我审查一下刚才提交的代码` 会加载code-reviewer/SKILL.md。
启动后进入交互式会话，输入 `quit`/`exit` 退出。

## 创建 Skill

运行agent_mock.py或者agent.py，会自动创建`.claude/skills/code-reviewer/SKILL.md`以及相关资源。

可以通过skill_env.py文件修改Skill的内容。

## 依赖

```bash
pip install pyyaml python-dotenv openai
```

## 许可证

MIT
