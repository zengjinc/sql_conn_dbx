#!/usr/bin/env python3
"""从 JSON/CSV 导入数据库连接到 DBX SQLite 数据库（对应 import-dbx-connections.sh）

用法:
  python3 import-dbx-connections.py --json connections.json [--db /path/to/dbx.db] [--dry-run]
  python3 import-dbx-connections.py --csv connections.csv [--db /path/to/dbx.db] [--dry-run]
"""

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid

def get_default_db():
    if os.environ.get("DBX_DB_PATH"):
        return os.environ["DBX_DB_PATH"]
    if os.path.exists("/mnt/c"):
        import glob
        matches = glob.glob("/mnt/c/Users/*/AppData/Roaming/com.dbx.app/dbx.db")
        if matches:
            return matches[0]
    return os.path.expanduser("~/.config/com.dbx.app/dbx.db")

DEFAULT_DB = get_default_db()

DRIVER_MAP = {
    "mysql": "mysql:MySQL",
    "postgres": "postgres:PostgreSQL",
    "sqlite": "sqlite:SQLite",
    "rqlite": "rqlite:rQLite",
    "redis": "redis:Redis",
    "duckdb": "duckdb:DuckDB",
    "clickhouse": "clickhouse:ClickHouse",
    "sqlserver": "sqlserver:SQL Server",
    "mongodb": "mongodb:MongoDB",
    "oracle": "oracle:Oracle",
    "elasticsearch": "elasticsearch:Elasticsearch",
    "qdrant": "qdrant:Qdrant",
    "milvus": "milvus:Milvus",
    "weaviate": "weaviate:Weaviate",
    "chromadb": "chromadb:ChromaDB",
    "doris": "doris:Doris",
    "starrocks": "starrocks:StarRocks",
    "manticoresearch": "manticoresearch:ManticoreSearch",
    "databend": "databend:Databend",
    "redshift": "redshift:Redshift",
    "dameng": "dameng:Dameng",
    "kingbase": "kingbase:Kingbase",
    "highgo": "highgo:HighGo",
    "vastbase": "vastbase:Vastbase",
    "goldendb": "goldendb:GoldenDB",
    "gaussdb": "gaussdb:GaussDB",
    "kwdb": "kwdb:KWDB",
    "yashandb": "yashandb:YashanDB",
    "databricks": "databricks:Databricks",
    "saphana": "saphana:SAP HANA",
    "teradata": "teradata:Teradata",
    "vertica": "vertica:Vertica",
    "firebird": "firebird:Firebird",
    "exasol": "exasol:Exasol",
    "opengauss": "opengauss:openGauss",
    "oceanbase-oracle": "oceanbase-oracle:OceanBase Oracle",
    "gbase": "gbase:GBase",
    "access": "access:Access",
    "h2": "h2:H2",
    "snowflake": "snowflake:Snowflake",
    "trino": "trino:Trino",
    "prestosql": "prestosql:PrestoSQL",
    "hive": "hive:Hive",
    "spark": "spark:Spark",
    "db2": "db2:DB2",
    "informix": "informix:Informix",
    "neo4j": "neo4j:Neo4j",
    "cassandra": "cassandra:Cassandra",
    "bigquery": "bigquery:BigQuery",
    "kylin": "kylin:Kylin",
    "sundb": "sundb:SunDB",
    "oscar": "oscar:Oscar",
    "tdengine": "tdengine:TDengine",
    "xugu": "xugu:XuGu",
    "iotdb": "iotdb:IoTDB",
    "etcd": "etcd:etcd",
    "zookeeper": "zookeeper:ZooKeeper",
    "nacos": "nacos:Nacos",
    "iris": "iris:IRIS",
    "turso": "turso:Turso",
    "cloudflare-d1": "cloudflare-d1:Cloudflare D1",
    "influxdb": "influxdb:InfluxDB",
    "questdb": "questdb:QuestDB",
    "jdbc": "jdbc:JDBC",
    "mq": "mq:MQ",
    # 别名
    "postgresql": "postgres:PostgreSQL",
    "mariadb": "mysql:MariaDB",
    "mssql": "sqlserver:SQL Server",
    "sqlite3": "sqlite:SQLite",
    "presto": "prestosql:Presto",
}


def get_m_subfolder(name):
    m = re.search(r'(m[12])', name)
    if m:
        return "M1" if m.group(1) == "m1" else "M2"
    return None


def determine_folder(host_name):
    name_lower = host_name.lower() if host_name else ""
    if "yanfa" in name_lower or "admin" in name_lower or "platform" in name_lower:
        return "Yanfa"
    if "cross" in name_lower:
        sub = get_m_subfolder(name_lower)
        return f"Cross/{sub}" if sub else "Cross"
    if "center" in name_lower:
        return "Center"
    if host_name and (host_name.startswith("Dev-") or host_name.startswith("Ali-") or host_name.startswith("Script-")):
        return "Dev"
    if "game" in name_lower:
        sub = get_m_subfolder(name_lower)
        return f"Game/{sub}" if sub else "Game"
    return "Game"


def build_ssh_layer(layer_id, host, port, user, auth, password, key_path, key_phrase, name,
                    enabled=True, timeout=5, expose_lan=False, use_agent=False, agent_sock=""):
    return {
        "type": "ssh",
        "id": layer_id,
        "name": name,
        "enabled": enabled,
        "host": host,
        "port": port,
        "user": user,
        "password": "",
        "key_path": key_path,
        "key_passphrase": "",
        "connect_timeout_secs": timeout,
        "expose_lan": expose_lan,
        "use_ssh_agent": use_agent,
        "ssh_agent_sock_path": agent_sock,
        "auth_method": auth,
    }


def build_config_json(conn_id, name, db_type, driver_profile, driver_label,
                      host, port, username, database, color,
                      transport_layers, conn_timeout, query_timeout,
                      idle_timeout, keepalive, ssl, url_params,
                      conn_str, jdbc_class, jdbc_paths=None):
    return {
        "id": conn_id,
        "name": name,
        "db_type": db_type,
        "driver_profile": driver_profile,
        "driver_label": driver_label,
        "url_params": url_params,
        "host": host,
        "port": port,
        "username": username,
        "password": "",
        "database": database if database else None,
        "color": color,
        "transport_layers": transport_layers,
        "connect_timeout_secs": conn_timeout,
        "query_timeout_secs": query_timeout,
        "idle_timeout_secs": idle_timeout,
        "keepalive_interval_secs": keepalive,
        "ssl": ssl,
        "sysdba": False,
        "connection_string": conn_str if conn_str else None,
        "external_config": None,
        "jdbc_driver_class": jdbc_class if jdbc_class else None,
        "jdbc_driver_paths": jdbc_paths or [],
    }


def import_connection(conn_data, db_path, dry_run, imported_connections):
    name = conn_data.get("name", "")
    if not name:
        return

    db_type = conn_data.get("db_type", "mysql")
    host = conn_data.get("host", "localhost")
    port = conn_data.get("port", 3306)
    username = conn_data.get("username", "")
    password = conn_data.get("password", "")
    database = conn_data.get("database", "")
    color = conn_data.get("color", "")
    folder = conn_data.get("folder", "")
    if not folder:
        folder = determine_folder(name)

    conn_timeout = conn_data.get("connect_timeout_secs", 10)
    query_timeout = conn_data.get("query_timeout_secs", 30)
    idle_timeout = conn_data.get("idle_timeout_secs", 60)
    keepalive = conn_data.get("keepalive_interval_secs", 30)
    ssl = conn_data.get("ssl", False)
    url_params = conn_data.get("url_params", "")
    conn_str = conn_data.get("connection_string", "")
    jdbc_class = conn_data.get("jdbc_driver_class", "")
    jdbc_paths = conn_data.get("jdbc_driver_paths", [])

    db_type_lower = db_type.lower()
    driver_entry = DRIVER_MAP.get(db_type_lower)
    if driver_entry:
        driver_profile, driver_label = driver_entry.split(":", 1)
    else:
        driver_profile = db_type_lower
        driver_label = db_type_lower

    # SSH layers
    ssh_layers = conn_data.get("ssh", []) or []
    transport = []
    ssh_secrets = []

    for layer in ssh_layers:
        layer_id = str(uuid.uuid4())
        shost = layer.get("host", "")
        sport = layer.get("port", 22)
        suser = layer.get("user", "")
        sauth = layer.get("auth_method", "key")
        spass = layer.get("password", "")
        skey = layer.get("key_path", "")
        sphrase = layer.get("key_passphrase", "")
        sname = layer.get("name", "SSH Tunnel")
        senable = layer.get("enabled", True)
        stimeout = layer.get("connect_timeout_secs", 5)
        slan = layer.get("expose_lan", False)
        suse_agent = layer.get("use_ssh_agent", False)
        sagent_sock = layer.get("ssh_agent_sock_path", "")

        transport.append(build_ssh_layer(
            layer_id, shost, sport, suser, sauth,
            spass, skey, sphrase, sname,
            senable, stimeout, slan, suse_agent, sagent_sock,
        ))

        if sauth == "key" and sphrase:
            ssh_secrets.append((f"transport_layer.{layer_id}.key_passphrase", sphrase))
        if sauth == "password" and spass:
            ssh_secrets.append((f"transport_layer.{layer_id}.password", spass))

    config = build_config_json(
        "", name, db_type, driver_profile, driver_label,
        host, port, username, database, color,
        transport, conn_timeout, query_timeout, idle_timeout,
        keepalive, ssl, url_params, conn_str, jdbc_class, jdbc_paths,
    )

    if dry_run:
        print(f"  [WHAT-IF] Would insert connection: {name}")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 按名称查找已有连接
    c.execute(
        "SELECT id FROM connections WHERE json_extract(config_json, '$.name') = ?",
        (name,),
    )
    row = c.fetchone()
    is_update = False
    if row:
        is_update = True
        conn_id = row[0]
        c.execute("DELETE FROM connection_secrets WHERE connection_id = ?", (conn_id,))
    else:
        conn_id = str(uuid.uuid4())

    config["id"] = conn_id
    config_json = json.dumps(config, separators=(",", ":"))

    if is_update:
        c.execute("UPDATE connections SET config_json = ? WHERE id = ?", (config_json, conn_id))
    else:
        c.execute("INSERT INTO connections (id, config_json) VALUES (?, ?)", (conn_id, config_json))

    # 连接密码
    if password:
        c.execute(
            "INSERT OR REPLACE INTO connection_secrets (connection_id, key, secret) VALUES (?, 'password', ?)",
            (conn_id, password),
        )

    # SSH 密钥/密码
    for sk, sv in ssh_secrets:
        c.execute(
            "INSERT OR REPLACE INTO connection_secrets (connection_id, key, secret) VALUES (?, ?, ?)",
            (conn_id, sk, sv),
        )

    conn.commit()
    conn.close()

    imported_connections.append((conn_id, folder))

    action = "UPDATE" if is_update else "NEW"
    print(f"  [{action}] {name} ({db_type} on {host}:{port})")


def update_sidebar_layout(db_path, imported_connections):
    if not imported_connections:
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT layout_json FROM sidebar_layout WHERE id=1")
    row = c.fetchone()
    layout_json_raw = row[0] if row else ""

    layout = None
    if layout_json_raw:
        try:
            layout = json.loads(layout_json_raw)
        except json.JSONDecodeError:
            layout = None

    groups = layout.get("groups", []) if layout else []
    order = layout.get("order", []) if layout else []

    path_to_entry = {}

    def index_group(entries, parent_segments):
        for e in entries:
            if e.get("type") != "group":
                continue
            segments = parent_segments + [e["id"]]
            grp = None
            for g in groups:
                if g["id"] == e["id"]:
                    grp = g
                    break
            if not grp:
                continue
            path_key = grp["name"] if not parent_segments else "/".join(parent_segments + [grp["name"]])
            path_to_entry[path_key] = e
            if "children" in e:
                index_group(e["children"], parent_segments + [grp["name"]])

    index_group(order, [])

    def ensure_group_path(segments):
        if not segments:
            return None
        parent = None
        path_so_far = []
        for seg in segments:
            path_so_far.append(seg)
            path_key = "/".join(path_so_far)
            if path_key in path_to_entry:
                parent = path_to_entry[path_key]
                continue
            group_id = str(uuid.uuid4())
            new_entry = {"type": "group", "id": group_id, "children": []}
            new_group = {"id": group_id, "name": seg, "collapsed": False}
            groups.append(new_group)
            path_to_entry[path_key] = new_entry
            if parent is not None:
                parent["children"].append(new_entry)
            else:
                order.append(new_entry)
            parent = new_entry
        return parent

    for conn_id, folder in imported_connections:
        conn_entry = {"type": "connection", "id": conn_id}
        if not folder:
            order.append(conn_entry)
        else:
            segments = [s.strip() for s in folder.split("/") if s.strip()]
            parent_entry = ensure_group_path(segments)
            if parent_entry is not None:
                parent_entry["children"].append(conn_entry)
            else:
                order.append(conn_entry)

    new_layout = {"groups": groups, "order": order}
    new_layout_json = json.dumps(new_layout, separators=(",", ":"))

    c.execute(
        "INSERT OR REPLACE INTO sidebar_layout (id, layout_json) VALUES (1, ?)",
        (new_layout_json,),
    )
    conn.commit()
    conn.close()

    print(f"  Sidebar layout updated with {len(imported_connections)} connection(s) in folders.")


def import_from_json(json_path, db_path, dry_run, imported_connections):
    with open(json_path, "r", encoding="utf-8") as f:
        connections = json.load(f)

    total = len(connections)
    print(f"Importing {total} connection(s) from JSON...")

    for i, conn_data in enumerate(connections, 1):
        print(f"[{i}/{total}] ", end="")
        import_connection(conn_data, db_path, dry_run, imported_connections)


def import_from_csv(csv_path, db_path, dry_run, imported_connections):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    print(f"Importing {total} connection(s) from CSV...")

    for i, row in enumerate(rows, 1):
        print(f"[{i}/{total}] ", end="")
        import_csv_row(row, db_path, dry_run, imported_connections)


def import_csv_row(row, db_path, dry_run, imported_connections):
    name = row.get("name", "").strip()
    if not name:
        return

    # 数字类型转换
    for k in ("port", "connect_timeout_secs", "query_timeout_secs", "idle_timeout_secs", "keepalive_interval_secs"):
        if k in row and row[k]:
            try:
                row[k] = int(row[k])
            except (ValueError, TypeError):
                pass
    if "ssl" in row and row["ssl"]:
        row["ssl"] = row["ssl"].strip().lower() == "true"

    # 解析 SSH 列 (SSH_HOST1, SSH_PORT1, ...)
    ssh_layers = []
    ssh_idx = 1
    while True:
        prefix = "SSH" if ssh_idx == 1 else f"SSH{ssh_idx}"
        host_key = f"{prefix}_HOST"
        if host_key not in row or not row.get(host_key, "").strip():
            break
        layer = {
            "host": row[host_key].strip(),
            "port": int(row.get(f"{prefix}_PORT", "22") or "22"),
            "user": row.get(f"{prefix}_USER", "").strip(),
            "auth_method": row.get(f"{prefix}_AUTH", "key").strip(),
        }
        if layer["auth_method"] == "key":
            if row.get(f"{prefix}_KEY_PATH", "").strip():
                layer["key_path"] = row[f"{prefix}_KEY_PATH"].strip()
            if row.get(f"{prefix}_KEY_PASSPHRASE", "").strip():
                layer["key_passphrase"] = row[f"{prefix}_KEY_PASSPHRASE"].strip()
        elif layer["auth_method"] == "password":
            if row.get(f"{prefix}_PASSWORD", "").strip():
                layer["password"] = row[f"{prefix}_PASSWORD"].strip()
        ssh_layers.append(layer)
        ssh_idx += 1

    if ssh_layers:
        row["ssh"] = ssh_layers

    # 清理空值
    clean = {}
    for k, v in row.items():
        if isinstance(v, str) and v.strip().lower() in ("", "none", "null"):
            clean[k] = ""
        else:
            clean[k] = v

    import_connection(clean, db_path, dry_run, imported_connections)


def main():
    parser = argparse.ArgumentParser(description="导入数据库连接到 DBX")
    parser.add_argument("--json", help="JSON 连接文件")
    parser.add_argument("--csv", help="CSV 连接文件")
    parser.add_argument("--db", default=DEFAULT_DB, help="dbx.db 路径")
    parser.add_argument("--ssh-config", help="SSH 配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = parser.parse_args()

    if not args.json and not args.csv:
        parser.error("请指定 --json 或 --csv")

    db_path = os.path.expanduser(args.db)
    if not os.path.isfile(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Using database: {db_path}")
    print()

    imported_connections = []

    if args.json:
        # --json 指定 connections.json 时自动生成
        if os.path.basename(args.json) == "connections.json":
            script_dir = os.path.dirname(os.path.abspath(__file__))
            gen_script = os.path.join(script_dir, "generate_connections.py")
            if os.path.isfile(gen_script):
                gen_args = ["--output", args.json]
                if args.ssh_config:
                    gen_args += ["--ssh-config", args.ssh_config]
                if args.dry_run:
                    gen_args += ["--dry-run"]
                subprocess.run([sys.executable, gen_script] + gen_args, check=True)
                print()
        import_from_json(args.json, db_path, args.dry_run, imported_connections)
    elif args.csv:
        import_from_csv(args.csv, db_path, args.dry_run, imported_connections)

    if not args.dry_run:
        update_sidebar_layout(db_path, imported_connections)

    print()
    print("Done.")


if __name__ == "__main__":
    main()
