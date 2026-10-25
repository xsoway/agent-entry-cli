# 发布与官方页

当前是本地发布准备版本。目标地址预配置为：

- 仓库：`https://github.com/xsoway/agent-entry-cli`
- Pages：`https://xsoway.github.io/agent-entry-cli/`

目标仓库尚未创建，以上链接不代表已上线。中文文档为用户选择，不要求切换成英文主 README。

## 本地查看

直接打开仓库根的 `index.html`，无需前端构建或联网加载资源。页面内文档链接使用相对路径，请保留仓库目录。也可在仓库根运行：

```bash
uv run --locked python -m http.server 8765 --bind 127.0.0.1
```

浏览器打开 `http://127.0.0.1:8765/`。静态预览服务仅供本地开发，结束后按 Ctrl+C 停止。

页面用法演示不执行模型或工具；本地时钟不是 Agent 指标。项目没有内置定时任务，因此未照搬参考站的自动化日程。

## 浏览器验收

官方页没有 JavaScript 运行依赖。以下 Playwright Core 仅为验收工具，放在临时目录，不加入 Python 或产品运行时依赖：

```bash
npm install --prefix /tmp/agent-entry-browser --ignore-scripts --no-audit --no-fund playwright-core@1.58.2
PLAYWRIGHT_MODULE=/tmp/agent-entry-browser/node_modules/playwright-core/index.mjs node scripts/verify_site.mjs
```

需要已安装的 Chrome 或 Chromium。脚本自动探测常见安装位置；其他位置通过 `CHROME_PATH` 指定。检查桌面／768px／380px、双语、命令、目录、Tweaks、时钟、动效及系统减少动效，要求控制台无错误、无外部运行资源请求。

要保存截图，可额外设置 `SITE_SCREENSHOT_DIR=/tmp/agent-entry-site-screens`。截图仅在验收时产生，默认不写入仓库。

## 发布提交门禁

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev pyright
uv build
uv run --locked --extra dev python scripts/verify_distribution.py
uv run --locked python scripts/check_release.py
```

分发检查默认允许从公开包索引获取解析元数据与依赖，以支持全新 CI 缓存；只有缓存完整时才使用 `scripts/verify_distribution.py --offline`。

`check_release.py` 要求完整、干净的提交，检查未忽略工作文件、可达历史 blob、commit/tag 消息与提交邮箱。Git 邮箱应使用准备公开的 GitHub noreply 地址；官方合成提交的 noreply 地址也允许。混合编码文件中的 ASCII 凭据仍会被检查。脚本发现问题只报告规则和位置，不打印匹配原文；即使历史中的凭据已从最新版本删除，也会失败。

该脚本只覆盖常见模式，不是全面 DLP 或依赖漏洞审计。分发归档需另做内容检查。检查不包含本地 reflog、不可达对象或未提供附件，分享源代码请使用干净 clone／源码包，勿直接复制 `.git` 目录。

## 托管前的操作

在用户明确授权公开发布后，再按实际仓库配置执行：

1. 创建目标仓库并设置 remote。填写 About、与实际功能一致的 topics；不把未实现的 Skills／多 Agent 能力作为标签。
2. 启用并验证 Private Vulnerability Reporting；将可用的私密入口记录到安全说明和发布检查。Discussions 与类别按需开启。
3. 推送完整提交，在 macOS/Linux CI 上确认测试、打包与独立安装通过。
4. Settings → Pages 选择 GitHub Actions；Actions 中手动执行 `Official page` 工作流。它只上传选定的公开文件，不上传 `.git`、环境、账本或构建缓存。
5. 读取工作流返回的真实 Pages URL，检查在线页面的版本、语言、主要交互、控制台及窄屏布局。只有这一步通过，才更新页面和文档中的待部署状态。
6. 确认包元数据中的仓库／主页／问题链接实际可达后，按需要发布 Release 并附 wheel/sdist；核实资产列表。当前不承诺 PyPI 发布。

Pages 工作流没有 push 触发器。生成源码、存在元数据 URL、构建成功，都不能替代线上验收。

## 本次备份与回滚

本地初始提交身份修复前已在项目外保存 Git bundle 与工作树归档。身份修复保持原提交树内容不变；备份包含修复前的私密身份，勿提交或公开。

本项目不自动删除 reflog、不强制推送、不修改全局 Git 配置。需要恢复历史或撤销完整交付时，用项目外备份进行本地恢复；不要在含其他工作的新现场直接强制覆盖。
