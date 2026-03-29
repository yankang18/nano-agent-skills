import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from prompts import base_system_prompt
from skill_env import setup_demo_environment
from skills import SkillRegistry
from tools import Tool, SkillTool, BashTool, ReadFileTool


class MockAgent(object):
    """
    Mock Agent - 模拟 Claude Code 的核心交互循环
    实现渐进披露的三级加载机制
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.tools: Dict[str, Tool] = {}
        self.context: Dict[str, Any] = {}  # 当前激活的 Skill 上下文
        self.conversation_history: List[Dict] = []

        # 注册工具
        self._register_tool(SkillTool(registry))
        self._register_tool(BashTool())
        # ReadFile 需要在运行时动态创建（因为依赖当前 context）

    def _register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def _get_system_prompt(self) -> str:
        """构建系统提示词（仅包含 Level 1 披露）"""
        return base_system_prompt.format(skills_registry=self.registry.get_registry_prompt())

    def _parse_model_output(self, output: str) -> Optional[Dict]:
        """解析模型的工具调用意图"""
        # 模拟模型输出：检查是否包含工具调用 JSON
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass

        # 简单的意图匹配（用于演示）
        if "Skill" in output and "code-reviewer" in output:
            return {"tool": "Skill", "params": {"command": "code-reviewer"}}
        elif "git diff" in output:
            return {"tool": "Bash", "params": {"command": "git diff", "description": "获取代码变更"}}
        elif "ReadFile" in output and "style-guide" in output:
            return {"tool": "ReadFile", "params": {"file_path": "references/style-guide.md"}}
        elif "lint.sh" in output:
            return {"tool": "Bash", "params": {"command": "bash scripts/lint.sh", "description": "运行代码检查"}}

        return None

    def _model_inference(self, user_input: str, available_info: str = "") -> str:
        """
        模拟 Claude 模型的推理过程
        展示模型如何基于 Skills Registry 判断意图
        """
        # 检查是否匹配 code-reviewer 的描述
        triggers = ["review", "审查", "检查代码", "看看这段代码"]
        if any(t in user_input.lower() for t in triggers):
            reasoning = f"""
[模型思考过程]
用户输入: "{user_input}"
检查 Skills Registry:
- 匹配到 **code-reviewer**: "在代码提交前进行审查，检查潜在bug...当用户提到'review'、'审查代码'...时触发"
→ 意图匹配！需要调用 Skill 工具加载完整指令。

[工具调用]
```json
{{
  "tool": "Skill",
  "params": {{"command": "code-reviewer"}}
}}
```
"""
            return reasoning

        return f"[模型思考] 未匹配到特定 Skill，直接回应用户: {user_input}"

    def run(self, user_input: str):
        """运行 Mock Agent，展示渐进披露全过程"""
        print("=" * 80)
        print(f"用户输入: {user_input}")
        print("=" * 80)

        # ---------------------------------------------
        # Level 1 启动加载SKILL.md中的元数据
        # ---------------------------------------------
        print("\n" + "=" * 80)
        print("Step 1: 启动加载 SKILL.md中的元数据【Level 1】")
        print("=" * 80)
        system_prompt = self._get_system_prompt()
        print(self.registry.get_registry_prompt())
        print(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        # ---------------------------------------------
        # Level 2 加载SKILL.md
        # ---------------------------------------------
        print("\n" + "=" * 80)
        print("Step 2: （模拟）模型基于 SKILL.md 元数据判断意图 【Level 2】")
        print("=" * 80)
        reasoning = self._model_inference(user_input)
        print(reasoning)
        tool_call = self._parse_model_output(reasoning)
        if tool_call and tool_call["tool"] == "Skill":
            print("\n" + "=" * 80)
            print("Step 3: 如果匹配到技能（Skill），使用Skill工具加载对应技能的Skills.md")
            print("=" * 80)
            skill_tool = self.tools["Skill"]
            result = skill_tool.execute(**tool_call["params"])

            # 保存上下文（Base Path 是关键）
            self.context = {
                "skill_name": result["command_name"],
                "base_path": result["base_path"],
                "skill_content": result["content"]
            }

            print(f"技能名称: {result['command_name']}")
            print(f"Base Path: {result['base_path']}")
            print(f"内容长度: {len(result['content'])} 字符")
            print("\n【SKILL.md 内容（已注入上下文）】")
            print(result['content'][:500] + "..." if len(result['content']) > 500 else result['content'])

            # 现在创建 ReadFile 工具（绑定当前 Base Path）
            readfile_tool = ReadFileTool()
            readfile_tool.set_context(self.context)
            self._register_tool(readfile_tool)

            # ---------------------------------------------
            # Level 3 执行 Skill 指令
            # ---------------------------------------------
            # Step 4: 执行 Skill 指令。模拟大模型执行 Skill 中的步骤.（通过工具调用）
            print("\n" + "=" * 80)
            print("Step 4: 按 Skill 指令执行【Level 3】")
            print("=" * 80)

            # 这里模拟大模型返回的结果是要调用3个工具
            execution_steps = [
                ("Bash", {"command": "git diff", "description": "获取代码变更"}),
                ("ReadFile", {"file_path": "references/style-guide.md"}),  # 相对路径！
                ("Bash", {"command": "scripts/lint.sh"}),  # 实际上是 Bash，这里演示路径解析
            ]

            for i, (tool_name, params) in enumerate(execution_steps, 1):
                print(f"\n执行步骤 {i}: {tool_name}({params})")

                if tool_name == "ReadFile":
                    # 展示 Level 3 披露：相对路径解析
                    full_path = Path(self.context['base_path']) / params['file_path']
                    print(f"  相对路径 '{params['file_path']}' 解析为: {full_path}")

                tool = self.tools.get(tool_name)
                if tool:
                    result = tool.execute(**params)
                    if result["status"] == "success":
                        content = result.get("content", result.get("stdout", ""))
                        preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"  结果: {preview}")
                    else:
                        print(f"  错误: {result.get('message', '')}")

        print("\n" + "=" * 80)
        print("任务完成")
        print("=" * 80)
        print("\n【披露层级总结】")
        print("Level 1: 始终保留 - Skills Registry (仅元数据)")
        print("Level 2: 触发加载 - SKILL.md 完整内容（一次性）")
        print("Level 3: 按需加载 - references/, scripts/ 等资源（执行时动态）")


if __name__ == "__main__":
    # 设置演示环境
    # print("初始化 Skill 环境...")
    # skills_dir = setup_demo_environment()

    # 创建 Agent
    skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = MockAgent(registry)

    # 运行示例：用户请求代码审查
    agent.run("帮我审查一下刚才提交的代码")

    print("\n" + "=" * 80)
    print("对比：如果没有渐进披露，系统提示词需要包含所有 Skill 的完整内容")
    print(f"当前 Skills 数量: {len(registry._skills)}")
    print(f"Level 1 披露大小: ~{len(registry.get_registry_prompt())} 字符")

    total_content = sum(len(s.content) for s in registry._skills.values())
    print(f"若全量加载需: ~{total_content} 字符")
    print(f"节省比例: {(1 - len(registry.get_registry_prompt()) / total_content) * 100:.1f}%")
