"""Single source of truth for application version.

- 版本号规则（semver 语义）：
  - 主版本 Major：架构 / 不兼容改动 / 里程碑大功能（如 2.0.0）
  - 次版本 Minor：新功能 / 重要改进（如 1.1.0）
  - 修订号 Patch：bug 修复 / 小优化 / 参数修正（如 1.0.1）
- 大更新升 Major，小更新升 Minor，修补升 Patch。
- 前端 build-info.json 的版本号在构建时引用本文件，保持单真相源一致。
"""

APP_VERSION = "1.0.11"