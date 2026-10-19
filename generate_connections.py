#!/usr/bin/env python3
"""从 SSH config 批量生成通用数据库连接配置 (sql_conn_dbx 格式)。

用法:
  python generate_connections.py [--ssh-config PATH] [--output PATH]

选项:
  --ssh-config PATH      SSH 配置文件路径 (默认: ~/.ssh/config)
  --output PATH          输出 JSON 文件路径 (默认: ./connections.json)
  --db-user USER         数据库用户名 (默认: game)
  --db-password PASSWORD 数据库密码 (默认使用 SSH config # pwd 注释)
  --default-db-type TYPE 默认数据库类型 (默认: mysql)
  --default-db-port PORT 默认数据库端口 (默认: 3306)
  --dry-run              只打印不写文件

从 SSH config 中提取的信息:
  - HostName        → SSH 目标主机
  - Port            → SSH 端口
  - User            → SSH 用户
  - IdentityFile    → SSH 私钥路径
  - # pwd           → 数据库密码
"""

import argparse
import json
import os
import re
import sys


def get_m_subfolder(host_name):
    m = re.match(r'(m[12])', host_name.lower())
    if m:
        return {'m1': 'M1', 'm2': 'M2'}.get(m.group(1))
    return None


def get_folder(host_name, entry=None):
    name_lower = host_name.lower()
    if entry and entry.get('db_user'):
        return 'Dev'
    if 'yanfa' in name_lower or 'admin' in name_lower or 'platform' in name_lower:
        return 'Yanfa'
    if 'cross' in name_lower:
        sub = get_m_subfolder(name_lower)
        return f'Cross/{sub}' if sub else 'Cross'
    if 'center' in name_lower:
        return 'Center'
    if host_name.startswith('Dev-') or host_name.startswith('Ali-') or host_name.startswith('Script-'):
        return 'Dev'
    if 'game' in name_lower:
        sub = get_m_subfolder(name_lower)
        return f'Game/{sub}' if sub else 'Game'
    return 'Game'


def parse_ssh_config_file(filepath, verbose=False):
    hosts = {}
    current_host = None
    current_config = {}

    expanded = os.path.expanduser(filepath)
    if verbose:
        print(f"  [DEBUG] 解析文件: {expanded}")

    try:
        with open(expanded, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        if verbose:
            print(f"  [DEBUG]   文件不存在，跳过")
        return hosts

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith('#') and not stripped.lower().startswith('# pwd') and not stripped.lower().startswith('# use'):
            continue

        if stripped.upper().startswith('HOST '):
            if current_host:
                hosts[current_host] = current_config
            host_name = stripped[5:].strip()
            if verbose:
                print(f"  [DEBUG]   发现 Host: {host_name}")
            current_host = host_name
            current_config = {}
        elif current_host:
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                key, value = parts[0].lower(), parts[1].strip()
                if key == 'hostname':
                    current_config['hostname'] = value
                elif key == 'user':
                    current_config['user'] = value
                elif key == 'port':
                    current_config['port'] = int(value)
                elif key == 'identityfile':
                    current_config['identityfile'] = os.path.expanduser(value)

        # 以下注释行在全局位置或 host 块内均可生效
        if stripped.lower().startswith('# pwd'):
            pwd_match = re.match(r'#\s*pwd\s+(.*)', stripped)
            if pwd_match:
                if current_host:
                    current_config['pwd'] = pwd_match.group(1).strip()
                elif verbose:
                    print(f"  [DEBUG]   忽略全局 # pwd（不归属于任何 Host）")
        if stripped.lower().startswith('# use'):
            user_match = re.match(r'#\s*user?\s+(.*)', stripped)
            if user_match:
                if current_host:
                    if verbose:
                        print(f"  [DEBUG]   解析 # user -> db_user={user_match.group(1).strip()} (用于 {current_host})")
                    current_config['db_user'] = user_match.group(1).strip()
                elif verbose:
                    print(f"  [DEBUG]   忽略全局 # user（不归属于任何 Host）")

    if current_host:
        hosts[current_host] = current_config

    return hosts


def collect_all_hosts(ssh_config_path, verbose=False):
    config_dir = os.path.dirname(os.path.expanduser(ssh_config_path))
    all_hosts = {}

    main_config = os.path.expanduser(ssh_config_path)
    if verbose:
        print(f"[DEBUG] 主配置文件: {main_config}")
        print(f"[DEBUG] 配置文件目录: {config_dir}")
    all_hosts.update(parse_ssh_config_file(main_config, verbose))

    include_patterns = []
    try:
        with open(main_config, 'r') as f:
            for line in f:
                m = re.match(r'Include\s+(.+)$', line.strip(), re.IGNORECASE)
                if m:
                    include_patterns.append(m.group(1).strip())
    except FileNotFoundError:
        if verbose:
            print(f"[DEBUG] 主配置文件不存在，不处理 Include")
        pass

    for pattern in include_patterns:
        if verbose:
            print(f"[DEBUG] Include 模式: {pattern}")
        if '*' in pattern or '?' in pattern:
            import glob
            base_dir = config_dir
            pattern_path = os.path.join(base_dir, pattern)
            matched_files = glob.glob(os.path.expanduser(pattern_path))
            if verbose:
                print(f"[DEBUG]   通配展开: {matched_files}")
            for f in matched_files:
                if os.path.isfile(f):
                    all_hosts.update(parse_ssh_config_file(f, verbose))
        else:
            full_path = os.path.join(config_dir, pattern)
            full_path = os.path.expanduser(full_path)
            if os.path.isfile(full_path):
                all_hosts.update(parse_ssh_config_file(full_path, verbose))
            else:
                if verbose:
                    print(f"[DEBUG]   文件不存在，尝试相对路径: {pattern}")
                all_hosts.update(parse_ssh_config_file(pattern, verbose))

    return all_hosts


def normalize_path(path):
    if not path:
        return ''
    path = path.replace('\\', '/')
    if path.startswith('/mnt/c/'):
        path = 'C:/' + path[7:]
    elif path.startswith('/home/'):
        parts = path.strip('/').split('/')
        if len(parts) >= 2:
            rel = '/'.join(parts[2:]) if len(parts) > 2 else ''
            import glob
            win_users = glob.glob('/mnt/c/Users/*')
            win_user = 'admin'
            for u in win_users:
                b = os.path.basename(u)
                if b not in ('All Users', 'Default', 'Default User', 'Public'):
                    win_user = b
                    break
            path = f'C:/Users/{win_user}/{rel}'
    return path.replace('/', '\\')


def build_ssh_entry(entry):
    ssh_host = entry.get('hostname', '')
    ssh_port = entry.get('port', 22)
    ssh_user = entry.get('user', '') or 'game'
    ssh_key = normalize_path(entry.get('identityfile', ''))

    ssh_item = {
        'host': ssh_host,
        'port': ssh_port,
        'user': ssh_user,
        'name': 'SSH Tunnel',
    }

    if ssh_key:
        ssh_item['auth_method'] = 'key'
        ssh_item['key_path'] = ssh_key
        ssh_item['key_passphrase'] = ''
    else:
        ssh_item['auth_method'] = 'password'
        ssh_item['password'] = ''

    return ssh_item


def build_connection(host_name, entry, db_user, db_password, db_type, db_port):
    ssh_entry = build_ssh_entry(entry)
    effective_db_user = entry.get('db_user') or db_user
    folder = get_folder(host_name, entry)

    conn = {
        'name': host_name,
        'folder': folder,
        'db_type': db_type,
        'host': 'localhost',
        'port': db_port,
        'username': effective_db_user,
        'password': db_password,
        'database': '',
        'ssh': [ssh_entry] if entry.get('hostname') else [],
    }

    return conn


def main():
    parser = argparse.ArgumentParser(description='从 SSH config 生成数据库连接配置')
    parser.add_argument('--ssh-config', default='~/.ssh/config',
                        help='SSH 配置文件路径')
    parser.add_argument('--output', default='./connections.json',
                        help='输出 JSON 文件路径')
    parser.add_argument('--db-user', default='game',
                        help='数据库用户名 (默认: game)')
    parser.add_argument('--db-password', default=None,
                        help='数据库密码 (默认使用 SSH config # pwd 注释)')
    parser.add_argument('--default-db-type', default='mysql',
                        help='默认数据库类型 (默认: mysql)')
    parser.add_argument('--default-db-port', type=int, default=3306,
                        help='默认数据库端口 (默认: 3306)')
    parser.add_argument('--allowed-users', nargs='*', default=None,
                        help='允许的 SSH 用户列表 (默认不限制)')
    parser.add_argument('--dry-run', action='store_true',
                        help='只打印不写文件')
    parser.add_argument('--verbose', action='store_true',
                        help='打印详细调试信息')
    args = parser.parse_args()

    all_hosts = collect_all_hosts(args.ssh_config, args.verbose)
    allowed_users = set(args.allowed_users) if args.allowed_users else None

    print(f"  找到 {len(all_hosts)} 个 SSH 主机配置")

    connections = []

    for host_name, entry in sorted(all_hosts.items()):
        ssh_user = entry.get('user', '') or 'game'

        if allowed_users and ssh_user not in allowed_users:
            if args.verbose:
                print(f"  [DEBUG] 跳过 {host_name}: SSH用户={ssh_user} 不在允许列表 {allowed_users}")
            continue

        if args.db_password is not None:
            db_pw = args.db_password
        else:
            db_pw = entry.get('pwd', '')

        conn = build_connection(host_name, entry, args.db_user, db_pw,
                                args.default_db_type, args.default_db_port)
        connections.append(conn)

        # ssh_info = conn['ssh'][0] if conn['ssh'] else None
        # if ssh_info:
        #     print(f"  [{conn['folder']:8s}] {host_name}")
        #     print(f"         SSH : {ssh_info['user']}@{ssh_info['host']:20s} :{ssh_info['port']}")
        #     if ssh_info['auth_method'] == 'key':
        #         print(f"         Key : {ssh_info['key_path']}")
        #     if db_pw:
        #         print(f"         DB  : {conn['username']}:{db_pw}")
        #     else:
        #         print(f"         DB  : {conn['username']}:<空密码>")
        #     print()

    if not connections:
        print("没有找到需要生成连接的主机。")
        return

    json_str = json.dumps(connections, indent=2, ensure_ascii=False)

    if args.dry_run:
        print("=" * 60)
        print(f"将写入 {args.output} ({len(connections)} 个连接)")
        print("=" * 60)
        print(json_str[:2000] + ("\n...(truncated)" if len(json_str) > 2000 else ""))
    else:
        with open(args.output, 'w') as f:
            f.write(json_str)
        print(f"  已写入: {os.path.abspath(args.output)} ({len(connections)} 个连接)")

    print(f"  共生成 {len(connections)} 个连接")


if __name__ == '__main__':
    main()
