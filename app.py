# Aethel V60+ — Advanced Local AI Platform
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from studio_grade import motion_html, roblox_files
from pathlib import Path
from urllib.parse import urlparse
import base64
import hashlib
import html
import json
import os
import random
import struct
import zlib
import re
import secrets
import sqlite3
import time
import zipfile
import shutil
import tempfile
import subprocess
import urllib.parse
import urllib.request
import resource

from ai_engine import AethelInference

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("AETHEL_DB_PATH", DATA_DIR / "aethel.db"))
PORT = int(os.environ.get("PORT", "5000"))
SESSION_DAYS = int(os.environ.get("AETHEL_SESSION_DAYS", "30"))
COOKIE_SECURE = os.environ.get("AETHEL_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"}
MAX_BODY = 14_000_000
MAX_CHAT = 20_000
MAX_CODE = 18_000
MAX_AGENT = 30_000
MAX_TOOL_INPUT = 12_000
MAX_PROJECT_FILES = int(os.environ.get("AETHEL_MAX_PROJECT_FILES", "80"))
MAX_PROJECT_BYTES = int(os.environ.get("AETHEL_MAX_PROJECT_BYTES", str(8 * 1024 * 1024)))
AGENT_MAX_STEPS = int(os.environ.get("AETHEL_AGENT_MAX_STEPS", "24"))
AUDIT_LOG = Path(os.environ.get("AETHEL_AUDIT_LOG", DATA_DIR / "audit.jsonl"))
WORKSPACE = Path(os.environ.get("AETHEL_WORKSPACE", DATA_DIR / "projects"))
WORKSPACE.mkdir(parents=True, exist_ok=True)

PBKDF2_ROUNDS = 310_000
CHECKOUT_BASIC = os.environ.get("AETHEL_CHECKOUT_BASIC", "").strip()
CHECKOUT_PRO = os.environ.get("AETHEL_CHECKOUT_PRO", "").strip()
ENTERPRISE_EMAIL = os.environ.get("AETHEL_ENTERPRISE_EMAIL", "sales@aethel.ai").strip()

BRAIN = AethelInference()

# Very small in-memory throttle for authentication endpoints.
RATE = {}
RATE_WINDOW = 60
RATE_LIMIT = 12
VISION_MAX_IMAGES = 4
VISION_MAX_BYTES = 5_000_000


def now() -> int:
    return int(time.time())


def db():
    con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def init_db():
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            model TEXT,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_chats_user_updated ON chats(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
        CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,key TEXT NOT NULL,value TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(user_id,key));
        CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id,updated_at DESC);
        CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,status TEXT NOT NULL,goal TEXT NOT NULL,project TEXT,steps INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,error TEXT);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id,updated_at DESC);
        CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,path TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(user_id,name));
        CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id,updated_at DESC);
        """
    )
    con.commit()
    con.close()


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    _, digest = hash_password(password, salt)
    return secrets.compare_digest(digest, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def rate_limited(key: str) -> bool:
    t = now()
    arr = RATE.setdefault(key, [])
    arr[:] = [x for x in arr if t - x < RATE_WINDOW]
    if len(arr) >= RATE_LIMIT:
        return True
    arr.append(t)
    return False


def parse_cookies(raw: str) -> dict[str, str]:
    out = {}
    for piece in raw.split(";"):
        if "=" not in piece:
            continue
        k, v = piece.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(40)
    t = now()
    con = db()
    con.execute("DELETE FROM sessions WHERE expires_at < ?", (t,))
    con.execute(
        "INSERT INTO sessions(user_id,token_hash,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?)",
        (user_id, hash_token(token), t, t + SESSION_DAYS * 86400, t),
    )
    con.commit()
    con.close()
    return token


def user_from_request(handler: BaseHTTPRequestHandler):
    auth = handler.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not token:
        cookies = parse_cookies(handler.headers.get("Cookie", ""))
        token = cookies.get("aethel_session", "")
    if not token:
        return None
    con = db()
    row = con.execute(
        "SELECT u.*, s.id AS session_id FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",
        (hash_token(token), now()),
    ).fetchone()
    if row:
        con.execute("UPDATE sessions SET last_seen_at=? WHERE id=?", (now(), row["session_id"]))
        con.commit()
    con.close()
    return dict(row) if row else None


def session_cookie(token: str, max_age: int) -> str:
    secure = "; Secure" if COOKIE_SECURE else ""
    return f"aethel_session={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax{secure}"


def origin_for(handler):
    origin = handler.headers.get("Origin")
    # Files opened directly in Chrome send Origin: null. It needs explicit CORS
    # so the local backend can be used from the tablet without moving the file.
    return "null" if origin == "null" else (origin or None)



def audit(user_id, action, detail=None):
    rec={"ts":now(),"user_id":user_id,"action":action,"detail":detail or {}}
    try:
        AUDIT_LOG.parent.mkdir(parents=True,exist_ok=True)
        with AUDIT_LOG.open("a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
    except Exception: pass

def safe_rel(root: Path, rel: str) -> Path:
    parts=[x for x in Path(str(rel)).parts if x not in ("", ".")]
    if any(x==".." for x in parts) or not parts: raise ValueError("caminho inválido")
    out=(root.joinpath(*parts)).resolve(); rr=root.resolve()
    if out != rr and rr not in out.parents: raise ValueError("caminho fora do workspace")
    return out

def project_stats(root: Path):
    files=[f for f in root.rglob("*") if f.is_file()]
    total=sum(f.stat().st_size for f in files)
    return {"files":len(files),"bytes":total}

def validate_project(root: Path):
    stats=project_stats(root)
    checks=[]
    checks.append({"name":"file-count","ok":stats["files"]<=MAX_PROJECT_FILES,"detail":stats})
    checks.append({"name":"project-size","ok":stats["bytes"]<=MAX_PROJECT_BYTES,"detail":stats})
    for py in root.rglob("*.py"):
        try:
            cp=subprocess.run([os.environ.get("PYTHON_BIN","python3"),"-m","py_compile",str(py)],cwd=str(root),capture_output=True,text=True,timeout=8)
            checks.append({"name":"python","file":str(py.relative_to(root)),"ok":cp.returncode==0,"stderr":cp.stderr[-2000:]})
        except Exception as e: checks.append({"name":"python","file":str(py.relative_to(root)),"ok":False,"stderr":str(e)})
    for html_file in root.rglob("*.html"):
        text=html_file.read_text(encoding="utf-8",errors="replace")
        checks.append({"name":"html","file":str(html_file.relative_to(root)),"ok":("<html" in text.lower() and "</html>" in text.lower())})
    return checks

def remember_project(user_id,name,root):
    con=db(); t=now(); con.execute("INSERT INTO projects(user_id,name,path,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET path=excluded.path,updated_at=excluded.updated_at",(user_id,name,str(root),t,t)); con.commit(); con.close()

def tool_execute(name, args, user_id, root=None):
    name=str(name or "").strip(); args=args if isinstance(args,dict) else {}
    if name=="calculator":
        expr=str(args.get("expression","")).strip()
        if len(expr)>500 or not re.fullmatch(r"[\d\s\+\-\*\/\%\(\)\.\^]+",expr): raise ValueError("expressão matemática inválida")
        value=eval(expr.replace("^","**"),{"__builtins__":{}},{})
        return {"ok":True,"value":value}
    if name=="execute_python":
        code=str(args.get("code","")).strip()
        if len(code)>MAX_CODE: raise ValueError("código grande demais")
        blocked=["import socket","import requests","urllib.request","os.system","subprocess.","shutil.rmtree","__import__","open('/etc","open(\"/etc"]
        if any(x in code for x in blocked): raise ValueError("código bloqueado")
        td=Path(tempfile.mkdtemp(prefix="aethel-tool-",dir=str(DATA_DIR))); f=td/"main.py"; f.write_text(code,encoding="utf-8")
        try:
            cp=subprocess.run([os.environ.get("PYTHON_BIN","python3"),str(f)],cwd=str(td),capture_output=True,text=True,timeout=8,env={"PATH":os.environ.get("PATH",""),"PYTHONIOENCODING":"utf-8"})
            return {"ok":cp.returncode==0,"exitCode":cp.returncode,"stdout":cp.stdout[-10000:],"stderr":cp.stderr[-10000:]}
        finally: shutil.rmtree(td,ignore_errors=True)
    if name=="list_files":
        if root is None: raise ValueError("workspace não disponível")
        files=[]
        for f in root.rglob("*"):
            if f.is_file(): files.append(str(f.relative_to(root)))
            if len(files)>=300: break
        return {"ok":True,"files":files}
    if name=="read_file":
        if root is None: raise ValueError("workspace não disponível")
        f=safe_rel(root,str(args.get("path",""))); return {"ok":True,"path":str(f.relative_to(root)),"content":f.read_text(encoding="utf-8")[:60000]}
    if name=="write_file":
        if root is None: raise ValueError("workspace não disponível")
        f=safe_rel(root,str(args.get("path",""))); content=str(args.get("content",""))
        if len(content)>60000: raise ValueError("arquivo grande demais")
        f.parent.mkdir(parents=True,exist_ok=True); f.write_text(content,encoding="utf-8"); return {"ok":True,"path":str(f.relative_to(root)),"bytes":len(content.encode())}
    raise ValueError("ferramenta desconhecida")

TOOL_SPECS=[
 {"name":"calculator","description":"Calcula expressões matemáticas simples","args":{"expression":"string"}},
 {"name":"execute_python","description":"Executa Python curto sem rede","args":{"code":"string"}},
 {"name":"list_files","description":"Lista arquivos do projeto atual","args":{}},
 {"name":"read_file","description":"Lê um arquivo do projeto atual","args":{"path":"string"}},
 {"name":"write_file","description":"Cria ou substitui um arquivo do projeto atual","args":{"path":"string","content":"string"}},
]

def web_search(query, limit=6):
    q=re.sub(r"\s+"," ",str(query or "").strip())[:500]
    if not q: return []
    url="https://html.duckduckgo.com/html/?q="+urllib.parse.quote(q)
    req=urllib.request.Request(url,headers={"User-Agent":"Aethel/60 (+local research assistant)"})
    with urllib.request.urlopen(req,timeout=8) as r: body=r.read().decode("utf-8","replace")
    results=[]
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',body,re.I|re.S):
        href=html.unescape(re.sub(r'<.*?>','',m.group(1)))
        title=html.unescape(re.sub(r'<.*?>','',m.group(2))).strip()
        if href.startswith('//'): href='https:'+href
        results.append({"title":title[:240],"url":href[:1000]})
        if len(results)>=limit: break
    return results

def web_context(query):
    try:
        rs=web_search(query)
        return "\n".join(f"- {x['title']} — {x['url']}" for x in rs), rs
    except Exception as exc:
        return f"Search unavailable: {type(exc).__name__}", []

def validate_images(images):
    if not images: return []
    if not isinstance(images,list) or len(images)>VISION_MAX_IMAGES: raise ValueError("Máximo de 4 imagens por mensagem.")
    out=[]
    for item in images:
        if not isinstance(item,str): continue
        if not item.startswith("data:image/"): continue
        head,_,payload=item.partition(',')
        raw=base64.b64decode(payload,validate=True)
        if len(raw)>VISION_MAX_BYTES: raise ValueError("Cada imagem deve ter no máximo 5 MB.")
        if not re.match(r"^data:image/(png|jpeg|jpg|webp);base64$",head,re.I): raise ValueError("Formato de imagem não suportado.")
        out.append(payload)
    return out

def sandbox_python(code):
    td=Path(tempfile.mkdtemp(prefix="aethel-sandbox-",dir=str(DATA_DIR)))
    f=td/"main.py"; f.write_text(code,encoding="utf-8")
    def limits():
        try:
            resource.setrlimit(resource.RLIMIT_CPU,(6,6)); resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024)); resource.setrlimit(resource.RLIMIT_FSIZE,(2*1024*1024,2*1024*1024)); resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
        except Exception: pass
    try:
        bwrap=shutil.which("bwrap")
        if bwrap:
            cmd=[bwrap,"--die-with-parent","--unshare-net","--new-session","--ro-bind","/usr","/usr","--ro-bind","/bin","/bin","--ro-bind","/lib","/lib","--ro-bind","/lib64","/lib64","--ro-bind","/etc","/etc","--proc","/proc","--dev","/dev","--tmpfs","/tmp","--ro-bind",str(f),"/sandbox/main.py","--chdir","/tmp",os.environ.get("PYTHON_BIN","python3"),"/sandbox/main.py"]
        else:
            cmd=[os.environ.get("PYTHON_BIN","python3"),str(f)]
        cp=subprocess.run(cmd,cwd=str(td),capture_output=True,text=True,timeout=8,env={"PATH":os.environ.get("PATH",""),"PYTHONIOENCODING":"utf-8"},preexec_fn=limits)
        return {"ok":cp.returncode==0,"exitCode":cp.returncode,"stdout":cp.stdout[-12000:],"stderr":cp.stderr[-12000:],"sandbox":"bubblewrap+network-isolated+resource-limits" if bwrap else "resource-limits-fallback"}
    except subprocess.TimeoutExpired: return {"ok":False,"error":"Tempo limite de 8s excedido.","sandbox":"timeout-enforced"}
    finally: shutil.rmtree(td,ignore_errors=True)

class Handler(BaseHTTPRequestHandler):
    server_version = "AethelServer/63.0"

    def _headers(self, content_type="application/json; charset=utf-8", cache=False):
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), payment=()")
        if not cache:
            self.send_header("Cache-Control", "no-store")
        origin = origin_for(self)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def j(self, obj, status=200, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self._headers()
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        if n > MAX_BODY:
            raise ValueError("payload muito grande")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except Exception as exc:
            raise ValueError("JSON inválido") from exc

    def file(self, name, ctype):
        path = ROOT / name
        if not path.exists():
            return self.j({"error": "arquivo não encontrado"}, 404)
        b = path.read_bytes()
        self.send_response(200)
        self._headers(ctype, cache=name.endswith(".png"))
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def client_key(self):
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/projects/download":
            user=user_from_request(self); q=urllib.parse.parse_qs(urlparse(self.path).query); name=Path(q.get("name",[""])[0]).name
            if not user or not name:return self.j({"error":"Download inválido."},400)
            path=WORKSPACE/(str(user["id"])+"-"+name)
            if not path.exists():return self.j({"error":"Projeto não encontrado."},404)
            b=path.read_bytes(); self.send_response(200); self._headers("application/zip",cache=False); self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if p == "/health":
            model_loaded = BRAIN.llm.configured
            models = BRAIN.llm.installed_models()
            return self.j({
                "ok": True,
                "version": "64.0.0",
                "database": "sqlite",
                "brain": "Aethel Core local",
                "trained_model": model_loaded,
                "model_version": BRAIN.llm.model if model_loaded else None,
                "training": None,
                "llm": {"available": model_loaded, "model": BRAIN.llm.model or None, "url": BRAIN.llm.url, "models": models, "error": BRAIN.llm.last_error or None},
                "image": {"mode": "diffusion" if os.environ.get("AETHEL_IMAGE_URL") else "local-raster", "configured": True, "fallback": True, "engine": "Aethel Local Raster" if not os.environ.get("AETHEL_IMAGE_URL") else "Aethel Local Diffusion"},
                "billing": bool(CHECKOUT_BASIC or CHECKOUT_PRO),
                "agent": {"max_steps": AGENT_MAX_STEPS, "tools": [x["name"] for x in TOOL_SPECS], "max_project_files": MAX_PROJECT_FILES, "max_project_bytes": MAX_PROJECT_BYTES},
                "persistence": {"memory": True, "projects": True, "audit": True},
                "vision": {"configured": bool(os.environ.get("AETHEL_VISION_MODEL","qwen2.5vl:3b").strip()), "model": os.environ.get("AETHEL_VISION_MODEL","qwen2.5vl:3b")},
                "web_search": {"enabled": True, "provider": "DuckDuckGo HTML"},
                "sandbox": {"enabled": True, "network_isolated": bool(shutil.which("bwrap")), "resource_limits": True},
            })
        if p == "/api/capabilities":
            llm=BRAIN.llm
            return self.j({"version":"64.0.0","codename":"Aethel Studio Grade — Creative + Motion + Roblox","local":True,"llm":{"configured":llm.configured,"model":llm.model or None,"url":llm.url},"features":{"streaming":True,"persistent_memory":True,"agent":True,"tool_use":True,"project_generation":True,"project_validation":True,"local_image_fallback":True,"web_search":True,"vision":True,"sandbox":True},"limits":{"agent_steps":AGENT_MAX_STEPS,"max_project_files":MAX_PROJECT_FILES,"max_project_bytes":MAX_PROJECT_BYTES}})
        if p == "/api/projects":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            con=db(); rows=con.execute("SELECT id,name,created_at,updated_at FROM projects WHERE user_id=? ORDER BY updated_at DESC LIMIT 100",(user["id"],)).fetchall(); con.close(); return self.j({"projects":[dict(r) for r in rows]})
        if p == "/api/agent/runs":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            con=db(); rows=con.execute("SELECT id,status,goal,project,steps,created_at,updated_at,error FROM agent_runs WHERE user_id=? ORDER BY updated_at DESC LIMIT 50",(user["id"],)).fetchall(); con.close(); return self.j({"runs":[dict(r) for r in rows]})
        if p == "/api/tools":
            return self.j({"tools":TOOL_SPECS,"execution_policy":"no-network, timeout=8s, workspace-bound writes, audited"})
        if p == "/api/auth/me":
            user = user_from_request(self)
            if not user:
                return self.j({"authenticated": False})
            return self.j({"authenticated": True, "user": {"id": user["id"], "name": user["name"], "email": user["email"], "plan": user["plan"]}})
        if p == "/api/model":
            installed=BRAIN.llm.installed_models()
            ready=BRAIN.llm.configured
            return self.j({"name": "Aethel Local LLM", "local": True, "trained": ready, "ready": ready, "version": BRAIN.llm.model or None, "installed": installed, "ollama": BRAIN.llm.url, "error": BRAIN.llm.last_error or None})
        if p == "/api/llm/status":
            installed=BRAIN.llm.installed_models()
            ready=BRAIN.llm.configured
            return self.j({"ok":True,"ready":ready,"model":BRAIN.llm.model or None,"visionModel":BRAIN.llm.vision_model or None,"installed":installed,"ollama":BRAIN.llm.url,"error":BRAIN.llm.last_error or None})
        if p == "/api/plans":
            return self.j({"currency": "BRL", "plans": {"free": {"price": 0}, "basic": {"price": 19.90, "checkout": bool(CHECKOUT_BASIC)}, "pro": {"price": 49.90, "checkout": bool(CHECKOUT_PRO)}, "enterprise": {"price": None, "contact": ENTERPRISE_EMAIL}}})
        if p == "/api/chats":
            user = user_from_request(self)
            if not user:
                return self.j({"error": "Autenticação necessária."}, 401)
            con = db()
            chats = con.execute("SELECT id,title,created_at,updated_at FROM chats WHERE user_id=? ORDER BY updated_at DESC", (user["id"],)).fetchall()
            out = []
            for c in chats:
                msgs = con.execute("SELECT role,content,model,created_at FROM messages WHERE chat_id=? ORDER BY id ASC LIMIT 100", (c["id"],)).fetchall()
                out.append({"id": str(c["id"]), "title": c["title"], "createdAt": c["created_at"], "updatedAt": c["updated_at"], "messages": [dict(m) for m in msgs]})
            con.close()
            return self.j({"chats": out})
        if p in ("/", "/index.html"):
            return self.file("index.html", "text/html; charset=utf-8")
        if p == "/aethel-logo.png":
            return self.file("aethel-logo.png", "image/png")
        self.send_response(404); self.end_headers()

    def sse_start(self):
        self.send_response(200); self._headers("text/event-stream; charset=utf-8",cache=False); self.send_header("Cache-Control","no-cache, no-transform"); self.send_header("Connection","close"); self.send_header("X-Accel-Buffering","no"); self.end_headers()
    def sse(self,obj):
        self.wfile.write(("data: "+json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n\n").encode()); self.wfile.flush()
    def _memory(self,user_id,limit=12):
        if not user_id:return []
        con=db(); rows=con.execute("SELECT value FROM memories WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",(user_id,limit)).fetchall(); con.close(); return [r[0] for r in rows]

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            d = self.read_json()
        except ValueError as exc:
            return self.j({"error": str(exc)}, 400)

        if p in ("/api/auth/register", "/api/auth/login") and rate_limited(self.client_key() + p):
            return self.j({"error": "Muitas tentativas. Tente novamente em um minuto."}, 429)

        if p == "/api/auth/register":
            name = re.sub(r"\s+", " ", str(d.get("name", "")).strip())[:80]
            email = normalize_email(d.get("email", ""))
            password = str(d.get("password", ""))
            if len(name) < 2: return self.j({"error": "Informe seu nome."}, 400)
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): return self.j({"error": "Email inválido."}, 400)
            if not (10 <= len(password) <= 128): return self.j({"error": "A senha deve ter de 10 a 128 caracteres."}, 400)
            salt, digest = hash_password(password)
            t = now()
            con = db()
            try:
                cur = con.execute("INSERT INTO users(name,email,password_hash,salt,created_at,updated_at) VALUES(?,?,?,?,?,?)", (name,email,digest,salt,t,t))
                user_id = cur.lastrowid
                con.commit()
            except sqlite3.IntegrityError:
                con.close(); return self.j({"error": "Este email já está cadastrado."}, 409)
            con.close()
            token = create_session(user_id)
            extra = {"Set-Cookie": session_cookie(token, SESSION_DAYS * 86400)}
            # When loaded as file://, cookie policies can differ; returning the token lets the client use Authorization.
            return self.j({"ok": True, "user": {"id": user_id, "name": name, "email": email, "plan": "free"}, "sessionToken": token if origin_for(self) == "null" else None}, 201, extra)

        if p == "/api/auth/login":
            email = normalize_email(d.get("email", "")); password = str(d.get("password", ""))
            con = db(); row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone(); con.close()
            if not row or not verify_password(password, row["salt"], row["password_hash"]):
                return self.j({"error": "Email ou senha incorretos."}, 401)
            token = create_session(row["id"])
            extra = {"Set-Cookie": session_cookie(token, SESSION_DAYS * 86400)}
            return self.j({"ok": True, "user": {"id": row["id"], "name": row["name"], "email": row["email"], "plan": row["plan"]}, "sessionToken": token if origin_for(self) == "null" else None}, 200, extra)

        if p == "/api/auth/logout":
            auth = self.headers.get("Authorization", "")
            token = auth[7:].strip() if auth.startswith("Bearer ") else parse_cookies(self.headers.get("Cookie", "")).get("aethel_session", "")
            if token:
                con = db(); con.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),)); con.commit(); con.close()
            return self.j({"ok": True}, 200, {"Set-Cookie": session_cookie("", 0)})

        if p == "/api/chat":
            # Guest mode is intentionally allowed: the local brain should answer a simple
            # "oi" without forcing account creation. Authenticated users additionally get
            # persistent conversations in SQLite.
            user = user_from_request(self)
            message = str(d.get("message", "")).strip()
            if not message or len(message) > MAX_CHAT:
                return self.j({"error": "Mensagem vazia ou grande demais."}, 400)
            chat_id_raw = d.get("conversationId")
            chat_id = None
            history = list(d.get("history") or [])[-12:]
            con = None
            if user:
                con = db()
                chat = None
                if chat_id_raw is not None:
                    try:
                        chat = con.execute("SELECT * FROM chats WHERE id=? AND user_id=?", (int(chat_id_raw), user["id"])).fetchone()
                    except Exception:
                        chat = None
                if not chat:
                    title = re.sub(r"\s+", " ", message)[:80] or "Nova conversa"
                    t = now(); cur = con.execute("INSERT INTO chats(user_id,title,created_at,updated_at) VALUES(?,?,?,?)", (user["id"], title, t, t)); chat_id = cur.lastrowid
                else:
                    chat_id = chat["id"]
                con.execute("INSERT INTO messages(chat_id,role,content,model,created_at) VALUES(?,?,?,?,?)", (chat_id, "user", message, str(d.get("modelMode", "Aethel Reasoning")), now()))
                history_rows = con.execute("SELECT role,content,model,created_at FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 12", (chat_id,)).fetchall()
                history = list(reversed([dict(r) for r in history_rows]))
                con.commit(); con.close(); con = None

            try:
                temperature = float(d.get("temperature", 0.7))
            except (TypeError, ValueError):
                temperature = 0.7
            assistant, meta = BRAIN.reply(message, history[:-1] if history else [], d.get("modelMode", "Aethel Reasoning"), temperature)
            if user and chat_id:
                con = db()
                con.execute("INSERT INTO messages(chat_id,role,content,model,created_at) VALUES(?,?,?,?,?)", (chat_id, "assistant", assistant, d.get("modelMode", "Aethel Reasoning"), now()))
                con.execute("UPDATE chats SET updated_at=? WHERE id=?", (now(), chat_id))
                con.commit(); con.close()
            return self.j({"reply": assistant, "conversationId": str(chat_id) if chat_id else None, "meta": meta, "authenticated": bool(user)})

        if p == "/api/chat/stream":
            user=user_from_request(self); message=str(d.get("message","")).strip()
            if not message or len(message)>MAX_CHAT:return self.j({"error":"Mensagem vazia ou grande demais."},400)
            history=list(d.get("history") or [])[-24:]; memory=self._memory(user["id"]) if user else []
            try: temperature=max(.05,min(float(d.get("temperature",.7)),1.2))
            except: temperature=.7
            try: images=validate_images(d.get("images") or [])
            except Exception as exc: return self.j({"error":str(exc)},400)
            search_results=[]; search_ctx=""
            if bool(d.get("webSearch")):
                search_ctx,search_results=web_context(message)
            BRAIN.llm.refresh()
            self.sse_start(); full=[]
            try:
                if search_results: self.sse({"type":"search","results":search_results})
                for chunk in BRAIN.stream(message,history,d.get("modelMode","Aethel Reasoning"),temperature,memory,images,search_ctx): full.append(chunk); self.sse({"type":"token","text":chunk})
                answer=''.join(full); self.sse({"type":"done","reply":answer})
            except Exception as exc:
                try:self.sse({"type":"error","error":str(exc),"model":BRAIN.llm.model or None,"ollama":BRAIN.llm.url})
                except:pass
            return
        if p == "/api/memory":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            action=str(d.get("action","list")); con=db()
            if action=="save":
                key=re.sub(r"[^a-zA-Z0-9_-]","_",str(d.get("key","memory")))[:80]; value=str(d.get("value","")).strip()[:1000]
                if not value:con.close();return self.j({"error":"Memória vazia."},400)
                t=now(); con.execute("INSERT INTO memories(user_id,key,value,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(user["id"],key,value,t,t)); con.commit()
            rows=con.execute("SELECT key,value,updated_at FROM memories WHERE user_id=? ORDER BY updated_at DESC LIMIT 100",(user["id"],)).fetchall(); con.close(); return self.j({"memories":[dict(r) for r in rows]})
        if p == "/api/tools":
            return self.j({"tools":TOOL_SPECS,"execution_policy":"no-network, timeout=8s, workspace-bound writes, audited"})
        if p == "/api/tools/execute":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            code=str(d.get("code","")).strip()
            if not code or len(code)>MAX_CODE:return self.j({"error":"Código vazio ou grande demais."},400)
            blocked=["import socket","import requests","urllib.request","os.system","subprocess.","shutil.rmtree","__import__","open('/etc","open(\"/etc"]
            if any(x in code for x in blocked):return self.j({"error":"Código bloqueado pela política de execução controlada."},400)
            result=sandbox_python(code); audit(user["id"],"sandbox_execute",{"sandbox":result.get("sandbox"),"ok":result.get("ok")}); return self.j(result,200 if result.get("ok") else 408)
        if p == "/api/search":
            q=str(d.get("query","")).strip()
            if not q:return self.j({"error":"query vazio"},400)
            ctx,results=web_context(q); return self.j({"query":q,"results":results,"provider":"DuckDuckGo HTML"})
        if p == "/api/motion":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            prompt=str(d.get("prompt","")).strip()[:12000]
            if not prompt:return self.j({"error":"Descreva a animação."},400)
            image_data=str(d.get("image","")).strip(); safe_prompt=html.escape(prompt,quote=True)
            img=image_data if image_data.startswith("data:image/") and len(image_data)<7_000_000 else ""
            name=re.sub(r"[^a-zA-Z0-9_-]+","-",prompt.lower()).strip("-")[:48] or "aethel-motion"
            html_out=motion_html(re.sub(r"[\r\n]+"," ",prompt)[:140],img,duration)
            root=WORKSPACE/(str(user["id"])+"-"+name);root.mkdir(parents=True,exist_ok=True);(root/"index.html").write_text(html_out,encoding="utf-8");(root/"MOTION_BRIEF.md").write_text(f"# Aethel Motion Studio\n\nPrompt: {prompt}\nEngine: GSAP + Three.js\n",encoding="utf-8")
            zp=WORKSPACE/(str(user["id"])+"-"+name+".zip")
            with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
                for f in root.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(root))
            return self.j({"ok":True,"mode":"motion","project":name,"preview":html_out,"download":"/api/projects/download?name="+urllib.parse.quote(zp.name),"features":["GSAP","Three.js","image animation","motion graphics","3D preview"]})
        if p == "/api/roblox":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            prompt=str(d.get("prompt","")).strip()[:12000]
            if not prompt:return self.j({"error":"Descreva o sistema Roblox."},400)
            name=re.sub(r"[^a-zA-Z0-9_-]+","-",prompt.lower()).strip("-")[:48] or "aethel-roblox-system";root=WORKSPACE/(str(user["id"])+"-roblox-"+name)
            (root/"src/ServerScriptService").mkdir(parents=True,exist_ok=True);(root/"src/StarterPlayer/StarterPlayerScripts").mkdir(parents=True,exist_ok=True);(root/"src/ReplicatedStorage/Shared").mkdir(parents=True,exist_ok=True)
            (root/"src/ServerScriptService/AethelServer.server.lua").write_text("""-- Aethel Roblox Game Engineering Engine
local Players=game:GetService("Players")
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local remote=Instance.new("RemoteEvent")
remote.Name="AethelAction"
remote.Parent=ReplicatedStorage
remote.OnServerEvent:Connect(function(player,action,payload)
 if typeof(action)~="string" then return end
 -- Server-authoritative validation and gameplay logic.
end)
Players.PlayerAdded:Connect(function(player) player:SetAttribute("AethelReady",true) end)
""",encoding="utf-8")
            (root/"src/StarterPlayer/StarterPlayerScripts/AethelClient.client.lua").write_text("""-- Aethel Roblox client controller
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local TweenService=game:GetService("TweenService")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
local remote=ReplicatedStorage:WaitForChild("AethelAction")
local function request(action,payload) remote:FireServer(action,payload) end
return {Request=request,TweenService=TweenService,Player=player}
""",encoding="utf-8")
            (root/"src/ReplicatedStorage/Shared/Config.lua").write_text(f'return {{Name={json.dumps(name)},Prompt={json.dumps(prompt)},Version="Aethel Game Engineering Engine 1.0"}}\n',encoding="utf-8");(root/"ROBLOX_BRIEF.md").write_text(f"# Aethel Roblox Game Engineering\n\nPrompt: {prompt}\n\nAuthorized Roblox Studio scaffold.\n",encoding="utf-8")
            for rel,content in roblox_files(name,prompt).items():
                target=root/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content,encoding="utf-8")
            zp=WORKSPACE/(str(user["id"])+"-roblox-"+name+".zip")
            with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
                for f in root.rglob('*'):
                    if f.is_file():z.write(f,f.relative_to(root))
            return self.j({"ok":True,"mode":"roblox","project":name,"files":[str(f.relative_to(root)) for f in root.rglob('*') if f.is_file()],"download":"/api/projects/download?name="+urllib.parse.quote(zp.name)})
        if p == "/api/agent":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            goal=str(d.get("goal","")).strip()
            if not goal or len(goal)>MAX_AGENT:return self.j({"error":"Objetivo inválido."},400)
            if not BRAIN.llm.configured:return self.j({"error":"O LLM local ainda não está disponível."},503)
            run_id=secrets.token_hex(8); name="aethel-project"; root=None; events=[]
            con=db(); t=now(); con.execute("INSERT INTO agent_runs(id,user_id,status,goal,created_at,updated_at) VALUES(?,?,?,?,?,?)",(run_id,user["id"],"RUNNING",goal,t,t)); con.commit(); con.close()
            try:
                awwwards_mode = bool(re.match(r"^\s*/(?:awwwards|aethel-awwwards)\b", goal, re.I))
                clean_goal = re.sub(r"^\s*/(?:awwwards|aethel-awwwards)\s*", "", goal, flags=re.I).strip() or "crie uma experiência web premium original"
                if awwwards_mode:
                    prompt="""You are Aethel Awwwards Creative Web Engine — a virtual multidisciplinary studio. Operate as Creative Director, Executive Art Director, Brand Designer, UX Architect, UI Designer, Motion Director, 3D/WebGL Director, Frontend Engineer, Performance Engineer, Accessibility Engineer, Visual QA and Code QA. Work with studio-level craft, not template-level output. Return ONLY JSON using this exact schema: {\"action\":\"tool|finish\",\"tool\":\"calculator|execute_python|list_files|read_file|write_file\",\"args\":{},\"message\":\"...\",\"project_name\":\"...\"}. Perform exactly ONE useful tool action per step. You must actually build a complete runnable website, not merely describe it. Use write_file for every project file. Prefer a polished static site that runs immediately, using CDN libraries when practical (GSAP, ScrollTrigger, Three.js/model-viewer) so it does not require a build step. For an Awwwards-mode project, first establish a coherent creative concept and then implement it through the files. The generated site should normally include: a strong preloader, distinctive hero, narrative scroll sections, editorial typography, responsive asymmetric composition, premium design tokens, product/content storytelling, microinteractions, custom cursor when appropriate, scroll-linked motion, GSAP/ScrollTrigger motion, optional 3D/WebGL or model-viewer when it materially improves the concept, image treatment with graceful fallbacks, navigation, CTA and footer. Include reduced-motion behavior, keyboard/focus states, mobile/tablet layouts, semantic HTML, and performance-conscious assets. Create an AWWWARDS_BRIEF.md documenting concept, art direction, UX architecture, motion language, typography, palette and section map. Do not copy any named site's design; make the work original while targeting a polished award-level creative-web standard. Iterate aggressively: inspect files, run structural QA, fix inconsistencies, validate HTML/CSS/JS, check responsive breakpoints, motion timing, focus states and performance. Do not stop at the first acceptable implementation. Reserve final steps for a deliberate polish pass and remove anything generic, accidental, repetitive or unfinished. The user gives only a basic brief; you expand it into the full creative system. Goal: """+clean_goal
                else:
                    prompt="""You are Aethel Agent. Return ONLY JSON. Schema: {\"action\":\"tool|finish\",\"tool\":\"calculator|execute_python|list_files|read_file|write_file\",\"args\":{},\"message\":\"...\",\"project_name\":\"...\"}. For tool, perform exactly one useful action. For finish, give a concise summary. Build a complete runnable project for the user's goal. Create files only through write_file. Goal: """+goal
                history=[]; memory=self._memory(user["id"])
                for step in range(AGENT_MAX_STEPS):
                    plan=BRAIN.llm.json_task(prompt,history,memory)
                    action=str(plan.get("action",""))
                    events.append({"step":step+1,"action":action,"message":str(plan.get("message",""))[:500]})
                    if action=="finish": break
                    if action!="tool": raise ValueError("ação do Agent inválida")
                    tool=str(plan.get("tool","")); args=plan.get("args") or {}
                    if tool=="write_file" and root is None:
                        name=re.sub(r"[^a-zA-Z0-9_-]","-",str(plan.get("project_name") or "aethel-project"))[:60] or "aethel-project"
                        root=WORKSPACE/(str(user["id"])+"-"+name); root.mkdir(parents=True,exist_ok=True)
                    if root is None and tool in {"list_files","read_file","write_file"}: raise ValueError("workspace ainda não criado")
                    if len(json.dumps(args,ensure_ascii=False)) > MAX_TOOL_INPUT: raise ValueError("entrada da ferramenta grande demais")
                    result=tool_execute(tool,args,user["id"],root)
                    con=db(); con.execute("UPDATE agent_runs SET steps=?,updated_at=?,project=? WHERE id=?",(step+1,now(),name,run_id)); con.commit(); con.close()
                    audit(user["id"],"agent_tool",{"run_id":run_id,"step":step+1,"tool":tool})
                    prompt=("Continue a tarefa. Retorne SOMENTE o mesmo JSON. Se estiver completo, use action=finish. Caso contrário, escolha uma única ferramenta. " + ("Você está em modo Awwwards: priorize completar e refinar o sistema visual, motion, responsividade e QA; não encerre apenas com documentação." if awwwards_mode else "") + " Objetivo: "+clean_goal+"\nResultado da ferramenta: "+json.dumps(result,ensure_ascii=False)[:18000])
                if root is None: raise ValueError("Agent terminou sem criar projeto")
                checks=validate_project(root)
                stats=project_stats(root)
                if stats["files"]>MAX_PROJECT_FILES or stats["bytes"]>MAX_PROJECT_BYTES: raise ValueError("projeto excedeu os limites de segurança")
                remember_project(user["id"],name,root)
                zip_path=WORKSPACE/(str(user["id"])+"-"+name+".zip")
                with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
                    for f in root.rglob("*"):
                        if f.is_file(): z.write(f,f.relative_to(root))
                audit(user["id"],"agent_complete",{"run_id":run_id,"project":name})
                con=db(); con.execute("UPDATE agent_runs SET status=?,steps=?,updated_at=?,project=? WHERE id=?",("COMPLETED",len(events),now(),name,run_id)); con.commit(); con.close()
                written=[str(f.relative_to(root)) for f in root.rglob("*") if f.is_file()]
                return self.j({"ok":True,"runId":run_id,"mode":"awwwards" if awwwards_mode else "standard","project":name,"files":written,"checks":checks,"events":events,"stats":stats,"download":"/api/projects/download?name="+urllib.parse.quote(zip_path.name)})
            except Exception as exc:
                audit(user["id"],"agent_error",{"run_id":run_id,"error":str(exc)})
                con=db(); con.execute("UPDATE agent_runs SET status=?,updated_at=?,error=? WHERE id=?",("FAILED",now(),str(exc)[:2000],run_id)); con.commit(); con.close()
                return self.j({"error":"Agent falhou.","detail":str(exc),"runId":run_id,"events":events},500)
        if p == "/api/billing/checkout":
            plan = str(d.get("plan", "")).lower(); urls = {"basic": CHECKOUT_BASIC, "pro": CHECKOUT_PRO}
            if plan == "enterprise": return self.j({"error": "Plano Enterprise: entre em contato com vendas.", "contact": ENTERPRISE_EMAIL})
            if plan not in urls or not urls[plan]: return self.j({"error": "Checkout não configurado neste servidor. Defina AETHEL_CHECKOUT_BASIC/PRO."}, 503)
            return self.j({"url": urls[plan], "plan": plan})
        if p == "/api/vision":
            user=user_from_request(self)
            if not user:return self.j({"error":"Autenticação necessária."},401)
            prompt=str(d.get("prompt","Descreva e analise a imagem com detalhes.")).strip()[:4000]
            try: images=validate_images(d.get("images") or [])
            except Exception as exc:return self.j({"error":str(exc)},400)
            if not images:return self.j({"error":"Envie pelo menos uma imagem."},400)
            try:
                answer,meta=BRAIN.reply(prompt,[],"Aethel Vision",float(d.get("temperature",.2)),[],images,None)
                return self.j({"reply":answer,"meta":meta,"vision":True})
            except Exception as exc:return self.j({"error":"Modelo de visão indisponível.","detail":str(exc)},503)
        if p == "/api/image":
            q = str(d.get("prompt", "")).strip()
            if not q: return self.j({"error": "prompt vazio"}, 400)
            try:
                result = generate_real_image(q, d.get("style", "cinematic"), d.get("aspect", "1:1"))
                # The local raster renderer is mandatory fallback, so this route should
                # never report "model not configured" merely because diffusion is absent.
                if result and result.get("imageBase64"):
                    return self.j(result, 200)
                fallback = local_raster_image(q, d.get("style", "cinematic"), d.get("aspect", "1:1"))
                return self.j(fallback, 200)
            except Exception as exc:
                # Last-resort renderer: keep the feature usable even if an optional
                # diffusion server or image dependency fails.
                try:
                    fallback = local_raster_image(q, d.get("style", "cinematic"), d.get("aspect", "1:1"))
                    fallback["warning"] = f"Diffusion indisponível: {type(exc).__name__}"
                    return self.j(fallback, 200)
                except Exception as fallback_exc:
                    return self.j({"error": "Falha no gerador local", "detail": str(fallback_exc)}, 500)
        return self.j({"error": "rota não encontrada"}, 404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        m = re.fullmatch(r"/api/chats/(\d+)", p)
        if not m: return self.j({"error": "rota não encontrada"}, 404)
        user = user_from_request(self)
        if not user: return self.j({"error": "Autenticação necessária."}, 401)
        try: d = self.read_json()
        except ValueError as exc: return self.j({"error": str(exc)}, 400)
        title = re.sub(r"\s+", " ", str(d.get("title", "")).strip())[:80]
        if not title: return self.j({"error": "Título vazio."}, 400)
        con = db(); cur = con.execute("UPDATE chats SET title=?,updated_at=? WHERE id=? AND user_id=?", (title, now(), int(m.group(1)), user["id"])); con.commit(); con.close()
        return self.j({"ok": cur.rowcount == 1})

    def do_DELETE(self):
        p = urlparse(self.path).path
        m = re.fullmatch(r"/api/chats/(\d+)", p)
        if not m: return self.j({"error": "rota não encontrada"}, 404)
        user = user_from_request(self)
        if not user: return self.j({"error": "Autenticação necessária."}, 401)
        con = db(); cur = con.execute("DELETE FROM chats WHERE id=? AND user_id=?", (int(m.group(1)), user["id"])); con.commit(); con.close()
        return self.j({"ok": cur.rowcount == 1})


def _png_bytes(width, height, pixels):
    raw = b''.join(b'\x00' + bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')


def local_raster_image(prompt, style="cinematic", aspect="1:1"):
    """Always-available local PNG renderer. It is a visual fallback, not a diffusion model."""
    sizes={"1:1":(768,768),"3:2":(960,640),"2:3":(640,960)}
    w,h=sizes.get(aspect,sizes['1:1'])
    # Premium gradient + spotlight + particles + product silhouette; no external service required.
    palettes={
        'cinematic':((5,6,10),(80,8,18),(230,230,235)),
        'editorial':((235,235,232),(65,65,70),(250,250,250)),
        'minimal':((8,9,12),(38,38,45),(245,245,245)),
        'futuristic':((3,8,20),(8,70,120),(130,225,255)),
    }
    a,b,c=palettes.get(style,palettes['cinematic'])
    px=[]
    seed=sum(ord(ch) for ch in prompt)%1000003
    rng=random.Random(seed)
    cx,cy=w//2,h//2
    for y in range(h):
        for x in range(w):
            dx=(x-cx)/(w*.72); dy=(y-cy)/(h*.72)
            glow=max(0.0,1.0-(dx*dx+dy*dy))
            edge=min(1.0,max(0.0,(abs(x-cx)/(w/2)+abs(y-cy)/(h/2))*.5))
            t=glow*.75
            r=int(a[0]*(1-t)+b[0]*t); g=int(a[1]*(1-t)+b[1]*t); bb=int(a[2]*(1-t)+b[2]*t)
            r=int(r*(1-edge*.25)); g=int(g*(1-edge*.25)); bb=int(bb*(1-edge*.25))
            px.extend((r,g,bb))
    # Add a stylized metallic object in the center, built directly into the PNG.
    def put(x,y,r,g,b):
        if 0<=x<w and 0<=y<h:
            i=(y*w+x)*3; px[i:i+3]=(r,g,b)
    left,right=int(cx-w*.12),int(cx+w*.12); top,bottom=int(cy-h*.27),int(cy+h*.27)
    for y in range(top,bottom):
        for x in range(left,right):
            nx=(x-cx)/(w*.12); ny=(y-cy)/(h*.27)
            if nx*nx+0.015*ny*ny <= 1:
                shine=max(0,1-abs(nx))*120
                rr=min(255,int(c[0]*.35+shine)); gg=min(255,int(c[1]*.35+shine)); bb=min(255,int(c[2]*.35+shine))
                if abs(ny)>.9: rr,gg,bb=180,185,190
                put(x,y,rr,gg,bb)
    # highlight bands and ambient particles
    for _ in range(max(120,w//4)):
        x=rng.randrange(w); y=rng.randrange(h)
        rad=rng.choice((1,1,2,3))
        for yy in range(y-rad,y+rad+1):
            for xx in range(x-rad,x+rad+1):
                if (xx-x)**2+(yy-y)**2<=rad*rad: put(xx,yy,220,220,225)
    data=_png_bytes(w,h,px)
    return {'prompt':prompt,'style':style,'aspect':aspect,'imageBase64':base64.b64encode(data).decode('ascii'),'created':int(time.time()*1000),'engine':'Aethel Local Raster'}


def generate_real_image(prompt, style="cinematic", aspect="1:1"):
    base=os.environ.get('AETHEL_IMAGE_URL','').strip().rstrip('/')
    sizes={"1:1":(1024,1024),"3:2":(1216,832),"2:3":(832,1216)}
    w,h=sizes.get(aspect,sizes['1:1'])
    style_text={'cinematic':'cinematic commercial photography, realistic lighting, detailed materials, professional composition','editorial':'high-end editorial photography, refined art direction, realistic materials','minimal':'minimal premium product photography, clean composition, realistic studio lighting','futuristic':'futuristic premium product photography, cinematic lighting, realistic materials'}.get(style,'cinematic')
    if base:
        payload=json.dumps({'prompt':f'{prompt}, {style_text}','negative_prompt':'blurry, low quality, distorted, duplicate, text artifacts, watermark','width':w,'height':h,'steps':28,'cfg_scale':6.5}).encode()
        req=urllib.request.Request(base+'/sdapi/v1/txt2img',data=payload,headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=float(os.environ.get('AETHEL_IMAGE_TIMEOUT','180'))) as r: data=json.loads(r.read().decode('utf-8','replace'))
            images=data.get('images') or []
            if images:
                return {'prompt':prompt,'style':style,'aspect':aspect,'imageBase64':images[0],'created':int(time.time()*1000),'engine':'Aethel Local Diffusion'}
        except Exception:
            pass
    # Never fail the UI just because an optional diffusion server is absent.
    return local_raster_image(prompt, style, aspect)

def make_svg(prompt, style="cinematic", aspect="1:1"):
    sizes={"1:1":(1024,1024),"3:2":(1200,800),"2:3":(800,1200)};w,h=sizes.get(aspect,sizes["1:1"]);p=html.escape(str(prompt)[:150]);cx=w/2;cy=h/2
    pal={"cinematic":("#050506","#1b1b22","#ffffff"),"editorial":("#f2f2f0","#17171a","#d7d7da"),"minimal":("#0b0b0c","#24242a","#f4f4f5"),"futuristic":("#050816","#16213c","#77d9ff")}.get(style,("#050506","#1b1b22","#fff"));bg,mid,fg=pal
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs><radialGradient id="b"><stop stop-color="{mid}"/><stop offset="1" stop-color="{bg}"/></radialGradient><linearGradient id="o"><stop stop-color="{fg}" stop-opacity=".9"/><stop offset=".5" stop-color="#777" stop-opacity=".35"/><stop offset="1" stop-color="{fg}" stop-opacity=".72"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#b)"/><ellipse cx="{cx}" cy="{cy+180}" rx="{w*.24}" ry="{h*.03}" fill="#000" opacity=".55"/><g transform="translate({cx-120} {cy-260}) rotate(-7 120 260)"><rect width="240" height="520" rx="80" fill="url(#o)" stroke="#fff" stroke-opacity=".18" stroke-width="3"/><ellipse cx="120" cy="25" rx="72" ry="18" fill="#aaa" opacity=".55"/><text x="120" y="275" text-anchor="middle" fill="#fff" font-family="Arial" font-size="28" font-weight="700">AETHEL</text></g><text x="{cx}" y="{h-74}" text-anchor="middle" fill="#fff" opacity=".78" font-family="Arial" font-size="{max(18,int(w/52))}">{p}</text><text x="{cx}" y="{h-38}" text-anchor="middle" fill="#fff" opacity=".38" font-family="Arial" font-size="14">AETHEL VISION • LOCAL GENERATOR</text></svg>'


if __name__ == "__main__":
    init_db()
    print(f"Aethel V64 local server: http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
