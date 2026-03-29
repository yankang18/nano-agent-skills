import json
from pathlib import Path
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

working_directory: Path = Path.cwd()

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

    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry
        self.tools: Dict[str, Tool] = {}
        self.conversation_history: List[Dict] = []

        # 注册工具
        self._register_tool(SkillTool(skill_registry))
        self._register_tool(BashTool())
        self._register_tool(ReadFileTool())

        # 初始化LLM
        self.llm_client = LLMClient()

        self._reset_agent_context()

    def _register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """构建系统提示词（仅包含 Level 1 披露）"""
        return base_system_prompt.format(skills_registry=self.skill_registry.get_registry_prompt())

    def _get_tool_schema(self):
        return [t.to_schema() for t in self.tools.values()]

    def _reset_agent_context(self):
        self.agent_context: Dict[str, Any] = {
            "working_directory": working_directory
        }

    def _set_skill_context(self, skill_context):
        self.agent_context["skill_context"] = skill_context

    def _model_inference(
            self,
            messages: List[Dict]
    ) -> dict:
        system_prompt = self._build_system_prompt()
        tool_schema = self._get_tool_schema()
        response = self.llm_client.inference(
            messages=messages,
            system_prompt=system_prompt,
            tool_schema=tool_schema)
        return response

    def _execute_tools(
            self,
            tool_calls: list[dict]
    ) -> list[dict]:
        tool_messages: list[dict] = []
        for tool_call in tool_calls:
            func_name = tool_call["function_name"]
            arguments = tool_call["arguments"]
            tool_call_id = tool_call["tool_call_id"]

            if func_name.upper() == "SKILL":
                skill_tool = self.tools["Skill"]
                tool_result = skill_tool.execute(**arguments)
                exec_status = tool_result["status"]

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(tool_result)
                })

                if exec_status == "succeed":
                    # 保存上下文（Base Path 是关键）
                    skill_name = tool_result["command_name"]
                    base_path = tool_result["base_path"]
                    skill_content = tool_result["content"]

                    self._set_skill_context({
                        "skill_name": skill_name,
                        "base_path": base_path,
                        "skill_content": skill_content
                    })

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
                tool.set_context(self.agent_context)
                tool_result = tool.execute(**arguments)

                print_info(f"工具结果: {tool_result}")

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(tool_result)
                })
        return tool_messages

    def run(self):
        """运行 Agent Loop，展示渐进披露全过程"""

        # ---------------------------------------------
        # Level 1
        # ---------------------------------------------
        print_info("\n" + "=" * 80)
        print_info("Step 1: 启动加载SKILL元数据【Level 1】")
        print_info("=" * 80)
        system_prompt = self._build_system_prompt()
        print_info(f"system_prompt:\n{system_prompt}")
        print_info(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        messages: list[dict] = []

        while True:
            # --- Step 1: 获取用户输入 ---
            try:
                # 输入"用户请求代码审查"观察效果
                user_input = input(colored_prompt()).strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{DIM}再见.{RESET}")
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "buy"):
                print(f"{DIM}再见.{RESET}")
                break

            self._reset_agent_context()

            print_info("=" * 80)
            print_info(f"用户输入: {user_input}")
            print_info("=" * 80)

            messages.append({"role": "user", "content": user_input})

            # --- Agent 内循环 ---
            # 模型可能连续调用多个工具才最终给出文本回复.
            # 用 while True 循环, 直到 stop_reason != "tool_calls"
            while True:

                # ---------------------------------------------
                # Level 2
                # ---------------------------------------------
                print_info("\n" + "=" * 80)
                print_info("Step 2: 模型基于用户输入和SKILL元数据判断意图【Level 2】")
                print_info("=" * 80)

                llm_response = self._model_inference(messages)
                print("=" * 80 + ">")
                try:
                    print_info(f"LLM result:\n{json.dumps(llm_response, ensure_ascii=False, indent=4)}")
                except:
                    print_info(f"LLM result: {llm_response}")
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
                    tool_messages = self._execute_tools(tool_calls)
                    messages.extend(tool_messages)
                    # 继续内循环 -- 模型会看到工具结果并决定下一步
                    continue

                elif stop_reason == "stop":
                    if content:
                        print_assistant(content)
                    # 跳出内循环, 等待下一次用户输入
                    break
                else:
                    print_info(f"[stop_reason={stop_reason}]")
                    if content:
                        print_assistant(content)
                    break

if __name__ == "__main__":
    # 设置演示环境
    # print("初始化 Skill 环境...")
    # skills_dir = setup_demo_environment()

    # 创建 Agent
    skills_dir = working_directory / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = AgentLoop(registry)

    # 运行示例
    agent.run()
