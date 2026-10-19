#!/usr/bin/env python3
"""从 DBX SQLite 数据库导出所有连接到 JSON（对应 export-dbx-connections.sh）

用法:
  python3 export-dbx-connections.py [--db /path/to/dbx.db] [--output export_connections.json]
"""

import argparse
import json
import sqlite3
import sys
import os

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

def determine_folder(name):
    name_lower = name.lower() if name else ""
    if "yanfa" in name_lower or "admin" in name_lower or "platform" in name_lower:
        return "Yanfa"
    if "cross" in name_lower:
        return "Cross"
    if "center" in name_lower:
        return "Center"
    if name and (name.startswith("Dev-") or name.startswith("Ali-") or name.startswith("Script-")):
        return "Dev"
    if "game" in name_lower:
        return "Game"
    return "Game"


def build_folder_map(layout_json):
    folder_map = {}
    if not layout_json:
        return folder_map
    try:
        layout = json.loads(layout_json)
    except json.JSONDecodeError:
        return folder_map

    groups = {g["id"]: g["name"] for g in layout.get("groups", [])}

    def traverse(entries, parent_path):
        result = {}
        for entry in entries:
            if entry.get("type") == "connection":
                result[entry["id"]] = parent_path
            elif entry.get("type") == "group":
                name = groups.get(entry.get("id", ""), "")
                child_path = name if not parent_path else parent_path + "/" + name
                result.update(traverse(entry.get("children", []), child_path))
        return result

    return traverse(layout.get("order", []), "")


def main():
    parser = argparse.ArgumentParser(description="导出 DBX 连接到 JSON")
    parser.add_argument("--db", default=DEFAULT_DB, help="dbx.db 路径")
    parser.add_argument("--output", default="export_connections.json", help="输出 JSON 路径")
    parser.add_argument("--pretty", action="store_true", help="格式化输出")
    args = parser.parse_args()

    db_path = os.path.expanduser(args.db)
    if not os.path.isfile(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Using database: {db_path}")
    print(f"Exporting to: {args.output}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT id, config_json FROM connections")
    rows = c.fetchall()

    c.execute("SELECT connection_id, key, secret FROM connection_secrets")
    secrets = {}
    for r in c.fetchall():
        secrets.setdefault(r["connection_id"], {})[r["key"]] = r["secret"]

    c.execute("SELECT layout_json FROM sidebar_layout WHERE id=1")
    layout_row = c.fetchone()
    folder_map = build_folder_map(layout_row["layout_json"] if layout_row else None)

    exported = []
    for row in rows:
        cid = row["id"]
        try:
            config = json.loads(row["config_json"])
        except json.JSONDecodeError:
            continue

        entry = {
            "name": config.get("name", ""),
            "db_type": config.get("db_type", "mysql"),
            "host": config.get("host", "localhost"),
            "port": config.get("port", 3306),
            "username": config.get("username", ""),
            "database": config.get("database") or "",
            "color": config.get("color", ""),
        }

        folder = folder_map.get(cid, "")
        if folder:
            entry["folder"] = folder
        elif entry["name"]:
            entry["folder"] = determine_folder(entry["name"])

        conn_secrets = secrets.get(cid, {})
        entry["password"] = conn_secrets.get("password", "")

        transport = config.get("transport_layers", [])
        ssh_list = []
        for layer in transport:
            if layer.get("type") != "ssh":
                continue
            lid = layer.get("id", "")
            ssh_entry = {
                "host": layer.get("host", ""),
                "port": layer.get("port", 22),
                "user": layer.get("user", ""),
                "auth_method": layer.get("auth_method", "key"),
                "name": layer.get("name", "SSH Tunnel"),
            }
            for k in ("key_path", "enabled", "connect_timeout_secs",
                      "expose_lan", "use_ssh_agent", "ssh_agent_sock_path"):
                v = layer.get(k)
                if v is not None and v != "":
                    ssh_entry[k] = v

            key_phrase = conn_secrets.get(f"transport_layer.{lid}.key_passphrase", "")
            if key_phrase:
                ssh_entry["key_passphrase"] = key_phrase
            layer_pass = conn_secrets.get(f"transport_layer.{lid}.password", "")
            if layer_pass:
                ssh_entry["password"] = layer_pass

            ssh_list.append(ssh_entry)

        entry["ssh"] = ssh_list
        exported.append(entry)

    conn.close()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(exported, f, indent=2 if args.pretty else None,
                  separators=None if args.pretty else (",", ":"),
                  ensure_ascii=False)

    print(f"Exported {len(exported)} connection(s) to {args.output}")


if __name__ == "__main__":
    main()
