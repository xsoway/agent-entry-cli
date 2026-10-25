# 发布修复与官方页验收记录

日期：2026-10-25。版本：0.1.0（Alpha）。使用用户指定的 oss-release-prep，保留用户要求的中文文档。

当前结论：本地代码、配置和官方页已完成修复验收。**源码仓库已公开，官方页已通过 GitHub Pages 部署；尚未发布 GitHub Release 或 PyPI 包。** 最终快照使用公开 noreply 提交身份；本地发布门禁与隔离检出验收见下文。

## 原检查项处理

| 原问题 | 修复及证据 | 状态 |
|---|---|---|
| P1：可达提交的私人邮箱 | 项目外 Git bundle／工作树归档备份后，初始提交替换为已核实 GitHub 账号的公开 noreply 身份；原提交 tree 保持一致。仅修改本仓库身份配置 | 本地修复；旧不可达对象可能仍留在 reflog，不直接分享 `.git` |
| P1：未跟踪新增模块／测试 | 本次发布快照纳入前序源码、终端回归、中文文档、官方页和发布检查；新增预检要求干净完整提交 | 完整本地提交；隔离检出复验 |
| P2：仓库／包链接缺失 | `pyproject.toml` 包含 Homepage、Repository、Issues；实际仓库与官方页已创建并读回验证 | 仓库／主页已公开，元数据目标对应实际服务 |
| P2：安全报告入口不明确 | 已启用 GitHub Private Vulnerability Reporting，API 读回 enabled 为 true；SECURITY.md 提供实际报告入口与无法使用时的处理方式 | 配置已启用并读回；未提交测试漏洞报告 |
| P2：IDE私有配置未忽略 | `.gitignore` 增加 `.vscode/`、`.idea/`、`_site/`；`.gitattributes` 统一行尾并声明二进制资源 | 本地修复 |
| 建议：导航／FAQ／维护入口 | README 新增目录、FAQ、维护入口、官方页、发布状态与操作说明 | 已补齐；主文档继续中文 |

## 官方页

入口：[index.html](index.html)。单文件内嵌 CSS、JS 和真实终端 SVG；无字体、脚本或图像 CDN 请求。

- [x] 指定 gruvbox 深底／金色；页面内容来自实际接口、版本与文档。
- [x] 中文默认；英文切换覆盖静态说明、动态命令与终端、标题与辅助文本。
- [x] 打字终端、执行路径循环高亮、原生目录展开、命令用法选择、Tweaks 颜色／动效与本地时钟。
- [x] 页面命令只说明用法，不执行模型／工具，不伪造业务输出。项目无定时任务，因此没有虚构日程。
- [x] Chrome 独立 headless 实测 1440／768／380px，无横向溢出；控制台无错误、无外部运行资源请求。
- [x] 系统减少动效、手动停止动效、语言切换后重绘、目录开关、配色和时钟检查通过。
- [x] 桌面和窄屏截图已人工查看；截图为项目外临时验收产物。

可重复命令与验收工具安装方式见 [docs/releasing.md](docs/releasing.md)。`scripts/verify_site.mjs` 使用独立的 Playwright Core，不增加本包运行时依赖。

## 发布门禁

新增 `scripts/check_release.py`，仅使用 Python 标准库。检查完整快照、可达 Git 历史、提交邮箱和常见内容泄露模式；输出规则与位置，不输出匹配值。

- [x] 真实临时 Git 仓库回归先 RED 后 GREEN：公开身份、私密身份、历史凭据、未提交源码、未跟踪敏感内容共十一项，覆盖官方 GitHub 合成／Dependabot 身份及公开签署、混合编码与 commit/tag 消息；审查发现均先 RED 后 GREEN。
- [x] CI 获取完整可达历史并执行发布预检。
- [x] Pages 工作流只有手动触发，最小权限部署，上传经过选择的公开文件，不包含 `.git`／环境／运行账本。
- [x] 形成完整本地提交；发布预检要求干净快照，隔离检出执行同一门禁与分发检查。

内容正则只覆盖常见 token、私钥、本机用户路径和邮箱，不是全面 DLP。法律署名和代码作者头是既有项目公开身份，不被擅自删除；不存在将版权署名当成私人邮箱豁免的规则。

## 远程发布状态

- [x] 公开仓库：[xsoway/agent-entry-cli](https://github.com/xsoway/agent-entry-cli)，默认分支 `main`，本地跟踪 `origin/main`。
- [x] About、Homepage 和 `agent`／`cli`／`llm`／`python` topics 已配置并读回；没有宣称未内置的 Skills／多 Agent 能力。
- [x] Private Vulnerability Reporting 已启用，实际报告入口见 [SECURITY.md](SECURITY.md)；没有发送测试报告。
- [x] 托管 macOS/Linux [CI 基线 b397789](https://github.com/xsoway/agent-entry-cli/actions/runs/40158249861) 通过，包括独立分发环境验证。
- [x] [Pages 部署基线 b397789](https://github.com/xsoway/agent-entry-cli/actions/runs/40158262388) 成功，地址为 [官方主页](https://xsoway.github.io/agent-entry-cli/)。网页字节与对应提交一致。
- [x] 线上交互门禁发现默认 favicon 请求 404；修复为内嵌品牌字符图标，不依赖额外文件。修复版本先通过本地浏览器门禁，最终线上复验按本次交付记录核对。
- [ ] Discussions 与类别按需配置；本次未发起社区讨论或公告。
- [ ] 用户要求发布版本时，再附 wheel/sdist 并读取 Release assets；未执行 GitHub Release 或 PyPI 发布。

## 本轮验证

- 全量测试：`97 passed in 72.85s`，包括原终端回归和 11 项发布预检用例。
- Ruff 检查及格式检查通过；Pyright 0 errors／0 warnings。
- `uv build` 成功，独立 uv 项目 wheel 安装、版本、init、diagnostics 与隔离导入通过。
- 官方页真实 Chrome headless 验收通过；四张 README Mermaid 图、Python 示例与本地文档引用检查通过。
- OpenSpec strict 和 `git diff --check` 通过。
- 独立审查发现的 1 P1／3 P2 均先补失败回归再修复；复审无遗留可操作 P0/P1/P2。详情见[审查记录](openspec/changes/release-readiness-site/review.md)。
- 发布快照以完整本地提交为准；预检检查工作树与可达历史，打包内容另行解包扫描。最终提交号与隔离检出机器结果记录在工作区任务验收记录，不在本文件自引用提交哈希。

托管 Linux/macOS 与页面部署已按上文基线实测。首次新环境发现离线解析缓存不足及 Dependabot 身份误报，已补回归修复并通过真实 CI。独立安装默认可联网，只有缓存完整时才显式使用 `--offline`。新的真实模型服务与业务权限效果仍需各自验收，不能从发布检查推断。

## 备份和边界

身份修复前的 bundle 和工作树归档位于项目外，包含旧私密身份，不应提交或共享。本地可达提交已改用公开身份；旧 reflog／不可达对象不在发布源码中，也未自动销毁。需要回滚时使用该备份，先确认没有后续新工作。

用户已授权创建与推送，仓库、源码、私密报告配置及 Pages 已按上文完成；没有发送公告、社区讨论或测试漏洞报告。后续操作见[发布说明](docs/releasing.md)。
