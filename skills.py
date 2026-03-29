from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class SkillMetadata:
    """Level 1: 轻量级元数据（始终保留在上下文）"""
    name: str
    description: str
    author: Optional[str] = None
    version: Optional[str] = None


@dataclass
class Skill:
    """完整技能对象（包含三级内容）"""
    metadata: SkillMetadata
    content: str  # Level 2: SKILL.md 正文
    base_path: Path  # 用于解析 Level 3 相对路径
    references: Dict[str, str] = field(default_factory=dict)  # Level 3: 引用文件缓存

    @property
    def name(self) -> str:
        return self.metadata.name


class SkillRegistry:
    """技能注册表 - 管理 Level 1 披露"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self):
        """启动时扫描所有技能，但只加载元数据（Level 1）"""
        if not self.skills_dir.exists():
            return

        # 遍历 skills 目标下的所有技能
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                # 寻找技能目录中的 SKILL.md 文件
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    # 加载 skill 的元数据（name, description）和内容
                    self._load_skill_metadata_and_content(skill_dir, skill_md)

    def _load_skill_metadata_and_content(self, skill_dir: Path, skill_md: Path):
        """仅解析 YAML frontmatter（约100 tokens）"""
        content = skill_md.read_text(encoding='utf-8')

        # 解析 YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1])
                    skill_content = parts[2].strip()

                    metadata = SkillMetadata(
                        name=meta.get('name', skill_dir.name),
                        description=meta.get('description', ''),
                        author=meta.get('author'),
                        version=meta.get('version')
                    )

                    # 只存储元数据，正文暂不进入上下文（Level 1 披露）
                    self._skills[metadata.name] = Skill(
                        metadata=metadata,
                        content=skill_content,  # 存储但不暴露给模型上下文
                        base_path=skill_dir
                    )
                except Exception as e:
                    print(f"加载技能失败 {skill_dir.name}: {e}")

    def get_registry_prompt(self) -> str:
        """生成 Skills Registry 部分（始终保留在系统提示词）"""
        lines = ["# 技能注册表（Skills Registry）\n",
                 "以下是你可用的技能列表。每个技能包含名称和描述。**当用户需求匹配某个技能的描述时，调用 `Skill` 工具加载完整指令**：\n"]

        for name, skill in self._skills.items():
            lines.append(f"1. **{name}**: {skill.metadata.description}")

        lines.append("\n如何使用技能：")
        lines.append("- 使用技能描述判断用户意图，而非仅匹配关键词")
        lines.append("- 只要意图相符，立即调用对应 Skill 工具，不要直接回应")
        lines.append("- 你不需要知道 Skill 的文件路径，只需传递技能名称给 Skill 工具")

        return "\n".join(lines)

    def load_full_skill(self, name: str) -> Optional[Skill]:
        """Level 2 披露：触发时加载完整 SKILL.md 内容"""
        return self._skills.get(name)

    def load_reference(self, skill_name: str, ref_path: str) -> Optional[str]:
        """Level 3 披露：按需加载引用文件"""
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        # 解析相对路径（基于 Base Path）
        full_path = skill.base_path / ref_path
        if full_path.exists():
            return full_path.read_text(encoding='utf-8')
        return None
