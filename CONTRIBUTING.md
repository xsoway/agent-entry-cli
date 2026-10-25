# 贡献指南

请先创建 Issue，说明可观察到的问题和建议的小范围改动。
修复缺陷前，先添加能够复现问题的最小失败回归测试。运行时与项目业务代码保持分离；
本包不得导入某个特定应用的 Core。

## 开发

需要 Python 3.13+ 和 uv。在仓库根目录执行：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev pyright
uv build
```

测试使用真实 SDK 和确定性的供应商替身，不需要 API 密钥。
测试真实模型时，使用环境变量提供凭据，并使用隔离的项目目录。
禁止提交模型密钥、原始私密对话或真实项目业务数据。
不得通过削弱取消、用量、作用域或未知写操作的回归测试来通过检查。

提交 Pull Request 时请说明问题、变更后的行为、相关测试输出和兼容性影响。
修改公共 API 或命令语义时同步更新文档。
新建 Python 文件沿用源码中的项目文件头格式。

## 发布隐私与官方页

请使用准备公开的 GitHub 用户名和 GitHub 设置中提供的 noreply 邮箱提交，避免把私人邮箱写入公开历史。不要复制其他人的邮箱；仅在本仓库配置自己的公开身份。

完整提交后运行 `uv run --locked python scripts/check_release.py`。预检检查干净快照、可达历史及常见敏感模式，失败报告不输出匹配原文。它不代替人工隐私复核或依赖安全审计。

官方页为根目录单文件 `index.html`。修改交互时按[发布说明](docs/releasing.md)运行真实浏览器验收；保留中文默认、完整英文切换、减少动效及窄屏布局。
