#!/usr/bin/env python3
"""删除 dbx.db 中所有连接及关联数据（对应 cleanup-connections.sh）

用法:
  python3 cleanup-connections.py [--db /path/to/dbx.db] [--dry-run]
"""

import argparse
import os
import sqlite3
import sys

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


def main():
    parser = argparse.ArgumentParser(description="删除 DBX 中所有连接")
    parser.add_argument("--db", default=DEFAULT_DB, help="dbx.db 路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印不执行")
    args = parser.parse_args()

    db_path = os.path.expanduser(args.db)
    if not os.path.isfile(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM connections")
    count_conn = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM connection_secrets")
    count_sec = c.fetchone()[0]

    print(f"数据库: {db_path}")
    print(f"  connections:        {count_conn} 条")
    print(f"  connection_secrets: {count_sec} 条")
    print()

    if count_conn == 0 and count_sec == 0:
        print("没有需要清理的数据。")
        return

    if args.dry_run:
        print("[DRY-RUN] 将执行以下操作:")
        print("  DELETE FROM connections;")
        print("  DELETE FROM connection_secrets;")
        print("  Reset sidebar_layout (清空 groups 和 order)")
    else:
        c.execute("DELETE FROM connections")
        c.execute("DELETE FROM connection_secrets")
        c.execute(
            "INSERT OR REPLACE INTO sidebar_layout (id, layout_json) VALUES (1, ?)",
            ('{"groups":[],"order":[]}',),
        )
        conn.commit()
        print("已删除所有连接，sidebar 布局已重置。")

    conn.close()


if __name__ == "__main__":
    main()
