from pathlib import Path
from typing import Dict, Any

from skills import SkillRegistry


class Tool:
    """工具基类"""

    def __init__(
            self,
            name: str,
            description: str,
            params: Dict[str, Any],
            required: list = None,
    ):
        self.name = name
        self.description = description
        self.params = params

        if required:
            self.required = required

        self.context = {}

    def set_context(self, context:Dict[str, Any]):
        self.context = context

    def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
        schema = {
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
        return schema


class SkillTool(Tool):
    """
    Skill 工具 - 渐进披露的关键机制
    接受技能名称，解析为实际文件路径，返回完整指令内容
    """

    def __init__(self, registry: SkillRegistry):
        super().__init__(
            name="Skill",
            description="加载技能（skills）完整指令。参数: {'command': '技能名称'}",
            params={"command": {"type": "string", "description": "技能名称，如 'code-reviewer'"}},
            required=["command"]
        )
        self.registry = registry

    def execute(self, command: str) -> Dict[str, Any]:
        """执行渐进披露 Level 2：加载完整 SKILL.md"""
        skill = self.registry.load_full_skill(command)

        if not skill:
            return {
                "status": "failed",
                "message": f"Skill '{command}' 不存在"
            }

        # 返回内容包含 Base Path，用于后续 Level 3 引用解析
        return {
            "status": "succeed",
            "message": f"Launching skill: {command}",
            "command_name": command,
            "base_path": str(skill.base_path),
            "content": skill.content,  # Level 2 披露：完整指令
            "note": "请按照上述指令执行。如需查阅引用文件（如 references/xxx.md），使用 ReadFile 工具并基于 Base Path 构造路径"
        }


class ReadFileTool(Tool):
    """ReadFile 工具 - 支持相对路径解析（Level 3 披露）"""

    def __init__(self):
        super().__init__(
            name="ReadFile",
            description="读取文件内容。支持绝对路径或基于当前 Skill Base Path 的相对路径",
            params={"file_path": {"type": "string"}},
            required=["file_path"]
        )

    def execute(
            self,
            file_path: str
    ) -> Dict[str, Any]:
        # 如果是相对路径，基于当前 Skill 的 Base Path 解析
        if not file_path.startswith('/') and self.context and self.context.get('base_path'):
            full_path = Path(self.context['base_path']) / file_path
        else:
            full_path = Path(file_path)

        if full_path.exists():
            content = full_path.read_text(encoding='utf-8')
            return {
                "status": "succeed",
                "content": content,
                "file_path": str(full_path)
            }
        return {
            "status": "failed",
            "message": f"文件不存在: {full_path}"
        }


class BashTool(Tool):
    """Bash 工具 - 执行命令"""

    def __init__(self):
        super().__init__(
            name="Bash",
            description="执行 shell 命令",
            params={"command": {"type": "string"}, "description": {"type": "string"}},
            required=["command"]
        )

    def execute(
            self,
            command: str,
            description: str = ""
    ) -> Dict[str, Any]:
        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "status": "succeed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "description": description
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": str(e)
            }
