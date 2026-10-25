# 只读知识助手

设置模型和凭据环境变量后，在仓库根目录运行：

```bash
uv run --locked agent-entry --project examples/knowledge --plugin examples/knowledge/project.py
```

提问示例：`在笔记中查找部署时间窗口，并引用文件名和行号。`

`search_notes` 只读取 `notes/*.md` 的直接子文件，跳过符号链接和超过 32 KiB 的文件，
最多扫描 100 个文件，最多返回 20 行匹配结果，不执行写操作。
文件系统检查以可信本地代码、没有恶意并发文件系统修改为前提，不构成操作系统沙箱。
