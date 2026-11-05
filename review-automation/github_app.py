"""Official GitHub App auth; Windows DPAPI storage and Node's built-in RS256."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import time

import controller as c


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != "nt":
        raise c.Stop("GitHub App key storage requires Windows DPAPI")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), "Local PR Review App", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise c.Stop("Windows DPAPI operation failed")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def save_secret(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(protect(json.dumps(value).encode()))
    temporary.replace(path)


def load_secret(path):
    return json.loads(protect(Path(path).read_bytes(), decrypt=True))


def app_client(config_path, repo):
    value = load_secret(config_path)
    node = shutil.which("node.exe") or shutil.which("node")
    if not node:
        raise c.Stop("Node.js is required for built-in GitHub App JWT signing")
    script = """const crypto=require('node:crypto');let input='';process.stdin.setEncoding('utf8');
process.stdin.on('data',x=>input+=x);process.stdin.on('end',()=>{const v=JSON.parse(input);
const b=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
const now=Math.floor(Date.now()/1000);const text=b({alg:'RS256',typ:'JWT'})+'.'+b({iat:now-60,exp:now+540,iss:String(v.client_id||v.id)});
const signature=crypto.sign('RSA-SHA256',Buffer.from(text),v.pem).toString('base64url');
process.stdout.write(text+'.'+signature);});"""
    response = c.run_process([node, "-e", script], input=json.dumps(value), timeout=15)
    if response.returncode:
        raise c.Stop("GitHub App JWT signing failed")
    auth = c.GitHub(repo, token=response.stdout.strip())
    app = auth.request("/app")
    if app["id"] != value["id"]:
        raise c.Stop("GitHub App identity mismatch")
    installation = auth.request(f"/repos/{repo}/installation")
    if installation["id"] != value["installation_id"]:
        raise c.Stop("GitHub App installation mismatch")
    permission = {"contents": "read", "issues": "read", "checks": "read", "statuses": "read", "pull_requests": "write"}
    token = auth.request(f"/app/installations/{value['installation_id']}/access_tokens", "POST",
        {"repositories": [repo.split('/')[1]], "permissions": permission})
    client = c.GitHub(repo, token=token["token"])
    client.actor = app["slug"] + "[bot]"
    return client
