# DBX 数据库连接管理工具集 (sql_conn_dbx)

批量管理、自动生成、导入/导出 DBX 数据库客户端连接配置的自动化工具集。

## 🎯 核心功能

- **从 SSH Config 自动生成连接配置** (`generate_connections.py`)：
  - 自动解析 `~/.ssh/config`（支持 `Include` 指令与通配符展开）。
  - 支持提取 SSH 跳板机、私钥路径、用户名及 `# pwd` 数据库密码注释。
  - 自动根据服务器命名规则对连接进行环境文件夹归类（Dev / Yanfa / Cross / Center / Game 等）。
- **批量导入到 DBX 客户端** (`import-dbx-connections.py`)：
  - 支持从 JSON 或 CSV 批量导入数据库连接与 SSH 隧道。
  - 自动维护 DBX 的 SQLite 数据库中的 `connections`、`connection_secrets` 及 `sidebar_layout`（侧边栏分组）。
  - 支持 50+ 种主流数据库驱动（MySQL、PostgreSQL、Redis、ClickHouse、Oracle、MongoDB 等）。
- **从 DBX 客户端导出配置** (`export-dbx-connections.py`)：
  - 将 DBX 客户端现有连接、秘钥及侧边栏分组导出为通用 JSON 格式。
- **快速重置与清理** (`cleanup-connections.py`)：
  - 一键清理 DBX 中的连接数据并重置侧边栏布局，支持 `--dry-run` 预览。

---

## 📁 目录结构

```text
.
├── generate_connections.py       # 从 SSH config 自动提取并生成连接 JSON
├── import-dbx-connections.py     # 将连接 JSON/CSV 导入到 DBX SQLite 数据库
├── export-dbx-connections.py     # 从 DBX SQLite 数据库导出连接到 JSON
├── cleanup-connections.py        # 清理 DBX 连接数据并重置布局
├── example-connections.json      # 连接配置文件示例
├── connections.example.json      # 标准连接模板
├── connections_custom.json       # 自定义/本地连接模板
└── README.md
```

---

## 🚀 快速上手

### 1. 从 SSH Config 生成连接配置

```bash
# 基本用法 (默认读取 ~/.ssh/config 并生成 connections.json)
python3 generate_connections.py

# 指定配置文件与数据库密码
python3 generate_connections.py \
  --ssh-config ~/.ssh/config \
  --output ./connections.json \
  --db-user game \
  --default-db-type mysql
```

> **SSH Config 注释说明**：可以在 SSH config 的 Host 块内添加注释，自动识别数据库账号密码：
> ```sshconfig
> Host Dev-MySQL
>     HostName 192.168.1.100
>     User jump_user
>     Port 22
>     IdentityFile ~/.ssh/id_rsa
>     # pwd your_db_password
>     # user your_db_user
> ```

### 2. 导入连接到 DBX 客户端

```bash
# 预览将要导入的内容 (不修改数据库)
python3 import-dbx-connections.py --json connections.json --dry-run

# 执行导入
python3 import-dbx-connections.py --json connections.json
```

可通过 `--db` 参数或 `DBX_DB_PATH` 环境变量指定 `dbx.db` 路径。

### 3. 从 DBX 导出连接

```bash
python3 export-dbx-connections.py --output my_backup.json --pretty
```

### 4. 清理所有连接

```bash
# 模拟执行
python3 cleanup-connections.py --dry-run

# 正式执行清空
python3 cleanup-connections.py
```

---

## 🔒 安全与脱敏规范

- `connections.json` 与 `export_connections.json` 包含真实服务器 IP、端口及明文密码，已被 `.gitignore` 严格忽略。
- 请勿将包含真实凭据的配置文件提交到公开仓库。
- 团队共享配置时，请使用 `connections.example.json` 作为模板，通过环境变量或安全配置中心分发真实密钥。

---

## 📄 License

MIT License
