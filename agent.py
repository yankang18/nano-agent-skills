import json
from typing import Dict, List, Any

from llms import LLMClient
from prompts import base_system_prompt
from skill_env import setup_demo_environment
from skills import SkillRegistry
from tools import Tool, SkillTool, BashTool, ReadFileTool

# ---------------------------------------------------------------------------
# ANSI 颜色
# ---------------------------------------------------------------------------
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def colored_prompt() -> str:
    return f"{CYAN}{BOLD}You > {RESET}"


def print_assistant(text: str) -> None:
    print(f"\n{GREEN}{BOLD}Assistant:{RESET} {text}\n")


def print_tool(name: str, detail: str) -> None:
    """打印工具调用信息."""
    print(f" {DIM}[tool: {name}] {detail}{RESET}")


def print_info(text: str) -> None:
    print(f"{DIM}{text}{RESET}")


class AgentLoop:
    """
    Agent Loop - 模拟 Claude Code 的核心交互循环
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
        self._register_tool(ReadFileTool())

        # 初始化LLM
        self.llm_client = LLMClient()

        self.current_skill_context = {}

    def _register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """构建系统提示词（仅包含 Level 1 披露）"""
        return base_system_prompt.format(skills_registry=self.registry.get_registry_prompt())

    def _get_tool_schema(self):
        return [t.to_schema() for t in self.tools.values()]

    def _model_inference(self, messages: List[Dict]) -> dict:
        system_prompt = self._build_system_prompt()
        tool_schema = self._get_tool_schema()
        response = self.llm_client.inference(
            messages=messages,
            system_prompt=system_prompt,
            tool_schema=tool_schema)
        return response

    def run(self, user_input: str):

        """运行 Agent Loop，展示渐进披露全过程"""
        print_info("=" * 80)
        print_info(f"用户输入: {user_input}")
        print_info("=" * 80)

        # ---------------------------------------------
        # Level 1
        # ---------------------------------------------
        print_info("\n" + "=" * 80)
        print_info("Step 1: 启动加载SKILL元数据【Level 1】")
        print_info("=" * 80)
        system_prompt = self._build_system_prompt()
        print_info(f"system_prompt:\n{system_prompt}")
        print_info(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        tool_schema = self._get_tool_schema()
        print(f"tool_schema: \n {json.dumps(tool_schema, ensure_ascii=False, indent=4)}")

        # ---------------------------------------------
        # Level 2
        # ---------------------------------------------
        print_info("\n" + "=" * 80)
        print_info("Step 2: 模型基于用户输入和SKILL元数据判断意图【Level 2】")
        print_info("=" * 80)
        messages: list[dict] = []

        self.current_skill_context = {}

        messages.append({
            "role": "user",
            "content": user_input,
        })

        while True:

            llm_response = self._model_inference(messages)
            print("=" * 80 + ">")
            print_info(f"LLM result:\n{json.dumps(llm_response, ensure_ascii=False, indent=4)}")
            print("<" + "=" * 80)

            status = llm_response["status"]
            if status == "failed":
                error_message = llm_response["error_message"]
                print_info(f"\n{YELLOW}API Error: {error_message}{RESET}\n")
                # 出错时回滚本轮所有消息到最近的 user 消息
                while messages and messages[-1]["role"] != "user":
                    messages.pop()
                if messages:
                    messages.pop()
                break

            # if status == "succeed":
            content = llm_response["content"]
            messages.append({"role": "assistant", "content": content})

            stop_reason = llm_response["stop_reason"]
            if stop_reason == "tool_calls":
                tool_calls = llm_response["tools"]
                for tool_call in tool_calls:
                    func_name = tool_call["function_name"]
                    arguments = tool_call["arguments"]
                    tool_call_id = tool_call["tool_call_id"]

                    if func_name.upper() == "SKILL":
                        skill_tool = self.tools["Skill"]
                        tool_result = skill_tool.execute(**arguments)
                        exec_status = tool_result["status"]

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": str(tool_result)
                        })

                        if exec_status == "succeed":
                            # 保存上下文（Base Path 是关键）
                            skill_name = tool_result["command_name"]
                            base_path = tool_result["base_path"]
                            skill_content = tool_result["content"]

                            self.current_skill_context = {
                                "skill_name": skill_name,
                                "base_path": base_path,
                                "skill_content": skill_content
                            }

                            print_info(f"调用SKILL:")
                            print_info(f"技能名称: {skill_name}")
                            print_info(f"Base Path: {base_path}")
                            print_info(f"内容长度: {len(skill_content)} 字符")
                            print_info("\n【SKILL.md 内容（已注入上下文）】")
                            print_info(skill_content[:500] + "..." if len(skill_content) > 500 else skill_content)

                    else:
                        # 执行工具
                        print_info(f"调用工具: {func_name}")
                        print_info(f"参数: {arguments}")
                        print_info(f"调用ID: {tool_call_id}")
                        tool = self.tools[func_name]
                        tool.set_context(self.current_skill_context)
                        tool_result = tool.execute(**arguments)

                        print_info(f"工具结果: {tool_result}")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": str(tool_result)
                        })

                # 继续内循环 -- 模型会看到工具结果并决定下一步
                continue

            elif stop_reason == "stop":
                if content:
                    print_assistant(content)
                self.current_skill_context = {}
                # 跳出内循环, 等待下一次用户输入
                break
            else:
                print_info(f"[stop_reason={stop_reason}]")
                self.current_skill_context = {}
                if content:
                    print_assistant(content)
                break


if __name__ == "__main__":
    # 设置演示环境
    print("初始化 Skill 环境...")
    skills_dir = setup_demo_environment()

    # 创建 Agent
    registry = SkillRegistry(skills_dir)
    agent = AgentLoop(registry)

    # 运行示例：用户请求代码审查
    agent.run("帮我审查一下刚才提交的代码")
    #
    # print("\n" + "=" * 80)
    # print("对比：如果没有渐进披露，系统提示词需要包含所有 Skill 的完整内容")
    # print(f"当前 Skills 数量: {len(registry._skills)}")
    # print(f"Level 1 披露大小: ~{len(registry.get_registry_prompt())} 字符")
    #
    # total_content = sum(len(s.content) for s in registry._skills.values())
    # print(f"若全量加载需: ~{total_content} 字符")
    # print(f"节省比例: {(1 - len(registry.get_registry_prompt()) / total_content) * 100:.1f}%")
