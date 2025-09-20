# aukpad.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, FileResponse
import json, secrets, string, time, os, threading, asyncio
from collections import defaultdict
from typing import Optional

app = FastAPI()
application = app  # alias if you prefer "application"

# Environment variables
USE_VALKEY = os.getenv("USE_VALKEY", "false").lower() == "true"
VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
MAX_TEXT_SIZE = int(os.getenv("MAX_TEXT_SIZE", "5")) * 1024 * 1024  # 5MB default
MAX_CONNECTIONS_PER_IP = int(os.getenv("MAX_CONNECTIONS_PER_IP", "10"))
RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "48"))  # Default 48 hours

# Valkey/Redis client (initialized later if enabled)
redis_client = None

# In-memory rooms: {doc_id: {"text": str, "ver": int, "peers": set[WebSocket], "last_access": float}}
rooms: dict[str, dict] = {}

# Rate limiting: {ip: [timestamp, timestamp, ...]}
rate_limits: dict[str, list] = defaultdict(list)

# Connection tracking: {ip: connection_count}
connections_per_ip: dict[str, int] = defaultdict(int)

def random_id(n: int = 4) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))

def init_valkey():
    global redis_client
    if USE_VALKEY:
        try:
            import redis
            redis_client = redis.from_url(VALKEY_URL, decode_responses=True)
            redis_client.ping()  # Test connection
            print(f"Valkey/Redis connected: {VALKEY_URL}")
        except ImportError:
            print("Warning: redis package not installed, falling back to memory-only storage")
            redis_client = None
        except Exception as e:
            print(f"Warning: Failed to connect to Valkey/Redis: {e}")
            redis_client = None

def get_room_data_from_cache(doc_id: str) -> Optional[dict]:
    if redis_client:
        try:
            data = redis_client.get(f"room:{doc_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Cache read error for {doc_id}: {e}")
    return None

def save_room_data_to_cache(doc_id: str, text: str, ver: int):
    if redis_client:
        try:
            data = {"text": text, "ver": ver, "last_access": time.time()}
            redis_client.setex(f"room:{doc_id}", RETENTION_HOURS * 3600, json.dumps(data))  # TTL in seconds
        except Exception as e:
            print(f"Cache write error for {doc_id}: {e}")

def update_room_access_time(doc_id: str):
    now = time.time()
    if doc_id in rooms:
        rooms[doc_id]["last_access"] = now
    
    if redis_client:
        try:
            data = redis_client.get(f"room:{doc_id}")
            if data:
                room_data = json.loads(data)
                room_data["last_access"] = now
                redis_client.setex(f"room:{doc_id}", RETENTION_HOURS * 3600, json.dumps(room_data))  # Reset TTL
        except Exception as e:
            print(f"Cache access update error for {doc_id}: {e}")

def cleanup_old_rooms():
    while True:
        try:
            now = time.time()
            cutoff = now - (RETENTION_HOURS * 3600)  # Convert hours to seconds
            
            # Clean in-memory rooms
            to_remove = []
            for doc_id, room in rooms.items():
                if room.get("last_access", 0) < cutoff and len(room.get("peers", set())) == 0:
                    to_remove.append(doc_id)
            
            for doc_id in to_remove:
                del rooms[doc_id]
                print(f"Cleaned up inactive room: {doc_id}")
            
            # Valkey/Redis has TTL, so it cleans up automatically
            
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        time.sleep(3600)  # Run every hour

def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    hour_ago = now - 3600
    
    # Clean old entries
    rate_limits[client_ip] = [t for t in rate_limits[client_ip] if t > hour_ago]
    
    # Check limit (50 per hour)
    if len(rate_limits[client_ip]) >= 50:
        return False
    
    # Add current request
    rate_limits[client_ip].append(now)
    return True

HTML = """<!doctype html>
<meta charset="utf-8"/>
<title>aukpad</title>
<style>
  :root { --line-h: 1.4; }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; padding: 0; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji","Segoe UI Emoji"; 
         max-width: 1000px; margin: 0 auto; padding: 1rem; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
  header { display:flex; justify-content:space-between; align-items:center; margin-bottom: .5rem; flex-shrink: 0; }
  a,button { padding:.35rem .6rem; text-decoration:none; border:1px solid #ddd; border-radius:8px; background:#fff; }
  #newpad { background:#000; color:#fff; border:1px solid #000; }
  #status { font-size:.9rem; opacity:.7; margin-left:.5rem; }
  #status::before { content: "●"; margin-right: .3rem; color: #ef4444; }
  #status.connected::before { color: #22c55e; }
  #wrap { display:grid; grid-template-columns: max-content 1fr; border:1px solid #ddd; border-radius:4px; overflow:hidden; 
          flex: 1; }
  #gutter, #t { font: 14px/var(--line-h) ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
  #gutter { padding:.5rem .75rem; text-align:right; color:#9ca3af; background:#f8fafc; border-right:1px solid #eee; 
            user-select:none; min-width: 3ch; white-space: pre; height: 100%; overflow: hidden; }
  #t { padding:.5rem .75rem; width:100%; height: 100%; resize: none; border:0; outline:0; 
       overflow:auto; white-space: pre; }
  #newpad { margin-left:.5rem; }
  pre {margin: 0; }
</style>
<header>
  <div>
    <strong id="padname"></strong><span id="status">disconnected</span>
  </div>
  <div>
    <button id="copy" onclick="copyToClipboard()">Copy</button>
    <a id="newpad" href="/">New pad</a>
  </div>
</header>
<div id="wrap">
  <pre id="gutter">1</pre>
  <textarea id="t" spellcheck="false" autocomplete="off" autocorrect="off" autocapitalize="off"
    placeholder="Start typing…"></textarea>
</div>
<script>
const $ = s => document.querySelector(s);
const proto = location.protocol === "https:" ? "wss" : "ws";
const rand = () => Math.random().toString(36).slice(2, 6); // 4 chars

// Derive docId from path; redirect root to random
let docId = decodeURIComponent(location.pathname.replace(/(^\\/|\\/$)/g, ""));
if (!docId) { location.replace("/" + rand() + "/"); }

$("#padname").textContent = "/"+docId+"/";

let ws, ver = 0, clientId = Math.random().toString(36).slice(2), debounce;

// --- Line numbers ---
const ta = $("#t");
const gutter = $("#gutter");
function updateGutter() {
  const lines = ta.value.split("\\n").length || 1;
  // Build "1\\n2\\n3..."
  let s = "";
  for (let i=1; i<=lines; i++) s += i + "\\n";
  gutter.textContent = s;
}
ta.addEventListener("input", updateGutter);
ta.addEventListener("scroll", () => { gutter.scrollTop = ta.scrollTop; });
// Also sync on keydown for immediate response
ta.addEventListener("keydown", () => { 
  setTimeout(() => { gutter.scrollTop = ta.scrollTop; }, 0); 
});

// --- WS connect + sync ---
function connect(){
  $("#status").textContent = "connecting…";
  $("#status").classList.remove("connected");
  ws = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(docId)}`);
  ws.onopen = () => { 
    $("#status").textContent = "connected";
    $("#status").classList.add("connected");
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "init") {
      ver = msg.ver; ta.value = msg.text; updateGutter();
    } else if (msg.type === "update" && msg.ver > ver && msg.clientId !== clientId) {
      const {selectionStart:s, selectionEnd:e} = ta;
      ta.value = msg.text; ver = msg.ver; updateGutter();
      ta.selectionStart = Math.min(s, ta.value.length);
      ta.selectionEnd   = Math.min(e, ta.value.length);
    }
  };
  ws.onclose = () => { 
    $("#status").textContent = "disconnected";
    $("#status").classList.remove("connected");
  };
}
$("#newpad").addEventListener("click", (e) => { e.preventDefault(); location.href = "/" + rand() + "/"; });

// Copy to clipboard function
async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(ta.value);
    const btn = $("#copy");
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  } catch (err) {
    // Fallback for older browsers
    ta.select();
    document.execCommand('copy');
    const btn = $("#copy");
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  }
}

connect();

// Handle Tab key to insert 4 spaces instead of navigation
ta.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    ta.value = ta.value.substring(0, start) + "    " + ta.value.substring(end);
    ta.selectionStart = ta.selectionEnd = start + 4;
    // Trigger input event to update line numbers and send changes
    ta.dispatchEvent(new Event('input'));
  }
});

// Send edits (debounced)
ta.addEventListener("input", () => {
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    if (ws?.readyState === 1) {
      ws.send(JSON.stringify({type:"edit", ver, text: ta.value, clientId}));
    }
  }, 120);
});
</script>
"""

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("favicon.ico")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url=f"/{random_id()}/", status_code=307)

@app.post("/", include_in_schema=False)
async def create_pad_with_content(request: Request):
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 50 requests per hour.")
    
    # Get and validate content
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Empty content not allowed")
    
    try:
        text_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Content must be valid UTF-8")
    
    # Check for null bytes
    if '\x00' in text_content:
        raise HTTPException(status_code=400, detail="Null bytes not allowed")
    
    # Check text size limit
    if len(text_content.encode('utf-8')) > MAX_TEXT_SIZE:
        raise HTTPException(status_code=413, detail=f"Content too large. Max size: {MAX_TEXT_SIZE} bytes")
    
    doc_id = random_id()
    rooms[doc_id] = {"text": text_content, "ver": 1, "peers": set(), "last_access": time.time()}
    
    # Save to cache if enabled
    save_room_data_to_cache(doc_id, text_content, 1)
    
    # Return URL instead of redirect for CLI usage
    base_url = str(request.base_url).rstrip('/')
    return PlainTextResponse(f"{base_url}/{doc_id}/\n")

@app.get("/{doc_id}/", response_class=HTMLResponse)
def pad(doc_id: str):
    # Update access time when pad is accessed
    update_room_access_time(doc_id)
    return HTMLResponse(HTML)

@app.get("/{doc_id}/raw", response_class=PlainTextResponse)
def get_raw_pad_content(doc_id: str):
    # Check in-memory rooms first
    if doc_id in rooms:
        update_room_access_time(doc_id)
        return PlainTextResponse(rooms[doc_id]["text"])
    
    # Check cache if not in memory
    cached_data = get_room_data_from_cache(doc_id)
    if cached_data:
        # Load into memory for future access
        rooms[doc_id] = {
            "text": cached_data.get("text", ""),
            "ver": cached_data.get("ver", 0),
            "peers": set(),
            "last_access": time.time()
        }
        update_room_access_time(doc_id)
        return PlainTextResponse(cached_data.get("text", ""))
    
    # Return empty content if pad doesn't exist
    return PlainTextResponse("")

async def _broadcast(doc_id: str, message: dict, exclude: WebSocket | None = None):
    room = rooms.get(doc_id)
    if not room: return
    dead = []
    payload = json.dumps(message)
    for peer in room["peers"]:
        if peer is exclude:
            continue
        try:
            await peer.send_text(payload)
        except Exception:
            dead.append(peer)
    for d in dead:
        room["peers"].discard(d)

@app.websocket("/ws/{doc_id}")
async def ws(doc_id: str, ws: WebSocket):
    # Get client IP for connection limiting
    client_ip = ws.client.host if ws.client else "unknown"
    
    # Check connection limit per IP
    if connections_per_ip[client_ip] >= MAX_CONNECTIONS_PER_IP:
        await ws.close(code=1008, reason="Too many connections from this IP")
        return
    
    await ws.accept()
    connections_per_ip[client_ip] += 1
    
    # Try to load room from cache first
    if doc_id not in rooms:
        cached_data = get_room_data_from_cache(doc_id)
        if cached_data:
            rooms[doc_id] = {
                "text": cached_data.get("text", ""),
                "ver": cached_data.get("ver", 0),
                "peers": set(),
                "last_access": time.time()
            }
    
    room = rooms.setdefault(doc_id, {"text": "", "ver": 0, "peers": set(), "last_access": time.time()})
    room["peers"].add(ws)
    
    # Update access time
    update_room_access_time(doc_id)
    
    await ws.send_text(json.dumps({"type": "init", "text": room["text"], "ver": room["ver"]}))
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            if data.get("type") == "edit":
                new_text = str(data.get("text", ""))
                
                # Check text size limit
                if len(new_text.encode('utf-8')) > MAX_TEXT_SIZE:
                    await ws.send_text(json.dumps({"type": "error", "message": f"Text too large. Max size: {MAX_TEXT_SIZE} bytes"}))
                    continue
                
                room["text"] = new_text
                room["ver"] += 1
                room["last_access"] = time.time()
                
                # Save to cache
                save_room_data_to_cache(doc_id, room["text"], room["ver"])
                
                await _broadcast(doc_id, {
                    "type": "update",
                    "text": room["text"],
                    "ver": room["ver"],
                    "clientId": data.get("clientId")
                })
    except WebSocketDisconnect:
        pass
    finally:
        room["peers"].discard(ws)
        # Decrement connection count for this IP
        connections_per_ip[client_ip] = max(0, connections_per_ip[client_ip] - 1)

# Initialize Valkey/Redis and cleanup thread on startup
@app.on_event("startup")
async def startup_event():
    init_valkey()
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_rooms, daemon=True)
    cleanup_thread.start()
    print("Aukpad started with cleanup routine")

# Run locally: uvicorn aukpad:app --reload

