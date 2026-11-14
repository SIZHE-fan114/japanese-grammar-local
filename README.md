**japanese-grammar-local 启动说明**

1. **环境准备（Python 3.11+）**
    - 创建虚拟环境并安装依赖：
        ```powershell
        python -m venv .venv
        .\.venv\Scripts\pip install -r requirements.txt
        ```
    - Linux / macOS：
        ```bash
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt
        ```

2. **启动程序**
    - **Windows 一键启动**（自动拉起服务并打开浏览器，默认访问 `http://127.0.0.1:18782/`）：
        ```powershell
        .\Start-JapaneseGrammar.ps1
        ```
    - **命令行直接启动**（跨平台通用）：
        ```powershell
        .\.venv\Scripts\python.exe -m tools.japanese_grammar.backend.main --host 127.0.0.1 --port 18782 --data-dir .runtime/japanese-grammar --web-dir tools/japanese_grammar/web
        ```
    - Linux / macOS 将命令中的 `.\.venv\Scripts\python.exe` 替换为 `.venv/bin/python` 后运行，再在浏览器打开 `http://127.0.0.1:18782/`。

3. **配置 AI 接口与数据目录说明（可选）**
    - 复制 `.env.example` 为 `.env` 并填写 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`，或启动后在页面右上角「AI 设置」直接填写并保存。
    - 本地学习进度（SQLite）与接口密钥保存在 `.runtime/japanese-grammar/` 及 `.env`，均已在 `.gitignore` 中忽略，不会上传到 Git。
