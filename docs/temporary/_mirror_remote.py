import json
import os
import posixpath
import shutil
import stat
from pathlib import Path
import paramiko

ROOT = Path(__file__).resolve().parents[2]
config = json.loads((ROOT / ".vscode" / "sftp.json").read_text(encoding="utf-8"))
remote_root = "/home/hzeng/project/ZH/MASKCO_v1"
exclude_dirs = {".git", ".vscode", "__pycache__", ".pytest_cache", ".mypy_cache", "saved_models", "results"}
exclude_suffixes = {".pyc", ".pyo"}
exclude_names = {".DS_Store", "Thumbs.db"}

def excluded(rel):
    p = Path(rel)
    return any(part in exclude_dirs for part in p.parts) or p.suffix in exclude_suffixes or p.name in exclude_names

def files():
    out = []
    for p in ROOT.rglob("*"):
        if p.is_file():
            rel = p.relative_to(ROOT).as_posix()
            if not excluded(rel):
                out.append((rel, p))
    return sorted(out)

def rm_tree(sftp, path):
    for e in sftp.listdir_attr(path):
        child = posixpath.join(path, e.filename)
        if stat.S_ISDIR(e.st_mode):
            rm_tree(sftp, child)
        else:
            sftp.remove(child)
    sftp.rmdir(path)

def mkdirs(sftp, path):
    parts = path.split("/")
    cur = ""
    for part in parts:
        if not part:
            continue
        cur += "/" + part
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)

client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(config["host"], port=config.get("port", 22), username=config["username"], password=config.get("password"), timeout=30, auth_timeout=30, banner_timeout=30)
sftp = client.open_sftp()
try:
    try:
        sftp.stat(remote_root)
        rm_tree(sftp, remote_root)
    except IOError:
        pass
    mkdirs(sftp, remote_root)
    local = files()
    total = sum(p.stat().st_size for _, p in local)
    done = 0
    for rel, p in local:
        dest = posixpath.join(remote_root, rel)
        mkdirs(sftp, posixpath.dirname(dest))
        sftp.put(str(p), dest)
        done += p.stat().st_size
        print(f"uploaded {len(rel):5d} chars path; {done}/{total} bytes", flush=True)
    print(f"SYNC_COMPLETE files={len(local)} bytes={total} remote={remote_root}", flush=True)
finally:
    sftp.close()
    client.close()
