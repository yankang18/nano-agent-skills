# Skill Progressive Disclosure 代码解析

基于 SkillPD 代码库的实现分析

---

## 1. 概述

### 1.1 问题背景

在 AI Agent 系统中，当可用技能（Skill）数量增多时，将所有 Skill 的完整指令一次性加载到 LLM 上下文会导致：

- **Token 消耗爆炸**：每个 Skill 可能包含数千 tokens 的指令
- **上下文窗口溢出**：超出模型上下文长度限制
- **推理质量下降**：无关信息干扰模型判断

### 1.2 核心思想

**渐进披露（Progressive Disclosure）** 借鉴 UI 设计中的信息分层理念，将 Skill 信息分为三级按需加载：

| 级别 | 内容 | 加载时机 | 典型大小 |
|------|------|----------|----------|
| Level 1 | 元数据（名称、描述） | 启动时常驻 | ~100 tokens |
| Level 2 | SKILL.md 完整指令 | 意图匹配时 | ~1000+ tokens |
| Level 3 | 引用文件（规范、脚本等） | 执行时按需 | 视文件大小 |

**收益**：相比全量加载，可节省 **80%+** 的上下文开销。

---

## 2. 核心组件

### 2.1 数据模型层

#### 2.1.1 SkillMetadata（Level 1）

```python
@dataclass
class SkillMetadata:
    """Level 1: 轻量级元数据（始终保留在上下文）"""
    name: str           # 技能名称
    description: str    # 触发条件描述
    author: Optional[str] = None
    version: Optional[str] = None
```

**设计要点**：
- 仅包含判断意图所需的最小信息
- 从 SKILL.md 的 YAML frontmatter 解析
- 常驻系统提示词，不占用工具调用上下文

#### 2.1.2 Skill（完整对象）

```python
@dataclass
class Skill:
    """完整技能对象（包含三级内容）"""
    metadata: SkillMetadata     # Level 1
    content: str                # Level 2: SKILL.md 正文
    base_path: Path             # 用于解析 Level 3 相对路径
    references: Dict[str, str]  # Level 3: 引用文件缓存
```

**关键字段 `base_path`**：
- 指向 Skill 目录的绝对路径
- 是 Level 3 相对路径解析的基准
- 在 SkillTool 执行后传递给后续工具

### 2.2 注册表层：SkillRegistry

```python
class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self._skills: Dict[str, Skill] = {}
        self._load_all_skills()  # 仅加载 Level 1
```

**核心方法**：

| 方法 | 职责 | 披露级别 |
|------|------|----------|
| `_load_skill_metadata()` | 解析 YAML frontmatter | Level 1 |
| `get_registry_prompt()` | 生成 Skills Registry 文本 | Level 1 |
| `load_full_skill()` | 返回完整 Skill 对象 | Level 2 |
| `load_reference()` | 基于 base_path 加载引用文件 | Level 3 |

### 2.3 工具层

#### 2.3.1 Tool 基类

```python
class Tool:
    def __init__(self, name: str, description: str, params: Dict, required: list):
        self.context = {}  # 运行时上下文
    
    def set_context(self, context: Dict[str, Any]):
        """动态注入当前 Skill 上下文"""
        self.context = context
    
    def to_schema(self) -> Dict:
        """生成 OpenAI Function Calling Schema"""
```

#### 2.3.2 SkillTool（Level 2 触发器）

```python
class SkillTool(Tool):
    """渐进披露的关键机制"""
    
    def execute(self, command: str) -> Dict:
        skill = self.registry.load_full_skill(command)
        return {
            "status": "succeed",
            "command_name": command,
            "base_path": str(skill.base_path),  # 关键：传递 base_path
            "content": skill.content,  # Level 2 披露
        }
```

**关键设计**：
- 通过 `Skill` 工具调用触发 Level 2
- 返回结果包含 `base_path`，为 Level 3 铺路

#### 2.3.3 ReadFileTool（Level 3 执行器）

```python
class ReadFileTool(Tool):
    """支持相对路径解析（Level 3 披露）"""
    
    def execute(self, file_path: str) -> Dict:
        # 相对路径基于当前 Skill 的 Base Path 解析
        if not file_path.startswith('/') and self.context.get('base_path'):
            full_path = Path(self.context['base_path']) / file_path
        ...
```

**关键设计**：
- 运行时通过 `set_context()` 注入当前激活的 Skill 上下文
- 相对路径自动解析为绝对路径

### 2.4 Agent 层

#### 2.4.1 AgentLoop（真实 LLM 交互）

```python
class AgentLoop:
    def __init__(self, skill_registry: SkillRegistry):
        self.tools = {}           # 工具注册表
        self.current_skill_context = {}  # 当前激活的 Skill 上下文
        
    def _execute_tools(self, tool_calls: list) -> list:
        for tool_call in tool_calls:
            if func_name.upper() == "SKILL":
                # Level 2 披露：保存上下文
                self.current_skill_context = {
                    "skill_name": result["command_name"],
                    "base_path": result["base_path"],
                    "skill_content": result["content"]
                }
            else:
                # Level 3 执行：注入上下文
                tool.set_context(self.current_skill_context)
                result = tool.execute(**arguments)
```

#### 2.4.2 MockAgent（演示用）

模拟模型输出，无需真实 LLM 调用，用于：
- 验证渐进披露流程
- 演示教学
- 单元测试

---

## 3. 执行流程

### 3.1 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           启动阶段                                       │
│  ┌─────────────────┐                                                    │
│  │ SkillRegistry   │ 扫描 .claude/skills/*                               │
│  │ _load_all_skills│ 解析每个 SKILL.md 的 YAML frontmatter                │
│  └────────┬────────┘                                                    │
│           │ Level 1: 仅加载元数据                                         │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ get_registry_   │ 生成 "技能注册表" 文本                                │
│  │ prompt()        │ 注入系统提示词（常驻上下文）                            │
│  └─────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          用户交互阶段                                     │
│                                                                         │
│  用户输入: "帮我审查代码"                                                   │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────┐                                                    │
│  │  模型推理        │ 基于 Level 1 的 Skills Registry 判断意图               │
│  │                 │ "code-reviewer: 在代码提交前进行审查..."               │
│  └────────┬────────┘                                                    │
│           │ 意图匹配                                                     │
│           ▼                                                             │
│  ┌─────────────────┐     ┌─────────────────┐                            │
│  │ SkillTool       │────▶│ load_full_skill │ 返回 SKILL.md 完整内容       │
│  │ execute()       │     │ (Level 2)       │                            │
│  └────────┬────────┘     └─────────────────┘                            │
│           │                                                             │
│           ▼                                                             │
│  保存 current_skill_context = {                                          │
│      "base_path": "/path/to/code-reviewer",                             │
│      "skill_content": "..."                                             │
│  }                                                                      │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │  模型按 Skill    │ 读取 "references/style-guide.md"                     │
│  │  指令执行        │ 运行 "bash scripts/lint.sh"                          │
│  │                 │                                                    │
│  └────────┬────────┘                                                    │
│           │ Level 3: 按需加载                                            │
│           ▼                                                             │
│  ┌─────────────────┐                                                    │
│  │ ReadFileTool    │ 相对路径 "references/style-guide.md"                │
│  │ set_context()   │ 解析为绝对路径                                       │
│  │ execute()       │                                                    │
│  └─────────────────┘                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 关键状态流转

```
初始状态
    │
    │ 启动扫描 Skills 目录
    ▼
┌─────────────┐
│ Level 1     │ 元数据常驻内存
│ (轻量级)     │ Skills Registry 在系统提示词中
└──────┬──────┘
       │ 用户输入触发意图匹配
       ▼
┌─────────────┐
│ Level 2     │ SKILL.md 完整内容加载
│ (一次性)     │ 注入当前对话上下文
└──────┬──────┘
       │ 按指令步骤执行
       ▼
┌─────────────┐
│ Level 3     │ 引用文件按需读取
│ (动态)       │ 基于 base_path 解析路径
└─────────────┘
```

---

## 4. 关键技术点

### 4.1 YAML Frontmatter 解析

SKILL.md 采用标准 frontmatter 格式：

```markdown
---
name: code-reviewer
description: 在代码提交前进行审查...
author: Claude Code Team
version: 1.0
---

## 工作流程
...
```

解析代码：

```python
parts = content.split('---', 2)
meta = yaml.safe_load(parts[1])      # Level 1
skill_content = parts[2].strip()     # Level 2
```

### 4.2 上下文传递机制

**问题**：ReadFileTool 如何知道当前激活的 Skill 目录？

**解决方案**：

1. SkillTool 执行后返回 `base_path`
2. Agent 保存到 `self.current_skill_context`
3. 其他工具执行前调用 `set_context()` 注入
4. ReadFileTool 使用 `context['base_path']` 解析相对路径

```python
# tools.py
class ReadFileTool(Tool):
    def execute(self, file_path: str):
        if not file_path.startswith('/') and self.context.get('base_path'):
            full_path = Path(self.context['base_path']) / file_path
```

### 4.3 工具 Schema 生成

自动生成 OpenAI Function Calling 格式：

```python
def to_schema(self) -> Dict:
    return {
        "type": "function",
        "function": {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.params,
                "required": self.required,
            },
        },
    }
```

---

## 5. 扩展指南

### 5.1 添加新 Skill

目录结构：

```
.claude/skills/{skill-name}/
├── SKILL.md              # 必须
├── references/           # 可选：Level 3 资源
│   └── guide.md
└── scripts/              # 可选：Level 3 资源
    └── check.sh
```

SKILL.md 模板：

```markdown
---
name: my-skill
description: 触发条件描述（这是 Level 1 内容）
author: Your Name
version: 1.0
---

## 工作流程
1. 读取 `references/guide.md`（Level 3）
2. 执行 `bash scripts/check.sh`（Level 3）
```

### 5.2 添加新工具

继承 `Tool` 基类：

```python
class MyTool(Tool):
    def __init__(self):
        super().__init__(
            name="MyTool",
            description="工具描述",
            params={"param1": {"type": "string"}},
            required=["param1"]
        )
    
    def execute(self, param1: str) -> Dict:
        # 可通过 self.context 获取当前 Skill 上下文
        return {"status": "succeed", "result": ...}
```

在 Agent 中注册：

```python
self._register_tool(MyTool())
```

---

## 6. 性能对比

假设系统有 10 个 Skill，每个 Skill 平均 2000 tokens：

| 方案 | 启动时上下文 | 单次请求最大上下文 | 节省比例 |
|------|-------------|-------------------|----------|
| 全量加载 | 20,000 tokens | 20,000 + 用户输入 | 0% |
| **渐进披露** | **~500 tokens** | **~2,500 + 用户输入** | **~87.5%** |

---

## 7. 总结

Skill Progressive Disclosure 通过三级信息分层，解决了 AI Agent 系统中技能膨胀导致的上下文爆炸问题：

1. **Level 1 元数据**：常驻内存，用于意图匹配
2. **Level 2 完整指令**：触发时加载，指导执行流程
3. **Level 3 引用资源**：按需读取，支持相对路径解析

**核心设计模式**：
- 注册表模式管理 Skill 生命周期
- 工具模式封装可执行能力
- 上下文传递实现跨工具协作

该架构具有良好的扩展性，支持动态添加 Skill 和工具，适用于构建大型、模块化的 AI Agent 系统。
