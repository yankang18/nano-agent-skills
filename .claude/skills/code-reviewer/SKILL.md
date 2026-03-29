---
name: code-reviewer
description: 在代码提交前进行审查，检查潜在bug、性能问题和风格违规。当用户提到"review code"、"review代码"、"审查代码"、"检查PR"或要求评估代码质量时触发。
author: Claude Code Team
version: 1.0
---

## 工作流程
执行代码审查时，严格遵循以下步骤：
1. **查阅规范**：读取 `references/style-guide.md`文件
2. **执行检查**：运行 `bash scripts/lint.sh`脚本
3. 输出审查报告

## 可用资源
- 规范文档：`references/style-guide.md`
- 检查脚本：`scripts/lint.sh`
  