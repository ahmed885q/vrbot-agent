#!/usr/bin/env python3
"""
VRBOT WebSocket Hub Server v1.0.0
Central relay between Dashboard and Python Agents.
"""
import asyncio, json, logging, time, argparse, ssl, os, signal
from collections import defaultdict

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("ERROR: pip install websockets"); raise

VERSION = "1.0.0"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WSHub")

class Registry:
    def __init__(self):
        self.dashboards = defaultdict(set)
        self.agents = {}
        self.ws_meta = {}
        self._lock = asyncio.Lock()

    async def register_dashboard(self, ws, uid):
        async with self._lock:
            self.dashboards[uid].add(ws)
            self.ws_meta[id(ws)] = {"role":"dashboard","userId":uid,"t":time.time()}
        logger.info(f"Dashboard connected: {uid} (total: {self.total_dashboards})")

    async def register_agent(self, ws, uid, did=None):
        async with self._lock:
            self.agents[id(ws)] = {"ws":ws,"userId":uid,"deviceId":did,"connectedAt":time.time()}
            self.ws_meta[id(ws)] = {"role":"agent","userId":uid,"deviceId":did,"t":time.time()}
        logger.info(f"Agent connected: {uid} dev={did} (total: {self.total_agents})")
        await self._notify_dash(uid, {"type":"agent_online","agentId":uid,"deviceId":did,"connectedAt":time.time()})

    async def unregister(self, ws):
        meta = self.ws_meta.pop(id(ws), None)
        if not meta: return
        async with self._lock:
            if meta["role"] == "dashboard":
                self.dashboards[meta["userId"]].discard(ws)
                if not self.dashboards[meta["userId"]]: del self.dashboards[meta["userId"]]
            elif meta["role"] == "agent":
                a = self.agents.pop(id(ws), None)
                if a:
                    await self._notify_dash(a["userId"], {"type":"agent_offline","agentId":a["userId"],"deviceId":a.get("deviceId")})

    async def _notify_dash(self, uid, msg):
        data = json.dumps(msg)
        for ws in list(self.dashboards.get(uid, set())):
            try: await ws.send(data)
            except: pass

    async def _notify_all_dash(self, msg):
        data = json.dumps(msg)
        for s in self.dashboards.values():
            for ws in s:
                try: await ws.send(data)
                except: pass

    async def send_to_agents(self, uid, msg):
        data = json.dumps(msg)
        for info in self.agents.values():
            if info["userId"] == uid:
                try: await info["ws"].send(data)
                except: pass

    def agents_for(self, uid):
        return [{"clientId":i["userId"],"deviceId":i.get("deviceId"),"connectedAt":i["connectedAt"]} for i in self.agents.values() if i["userId"]==uid]

    def all_agents(self):
        return [{"clientId":i["userId"],"deviceId":i.get("deviceId"),"connectedAt":i["connectedAt"]} for i in self.agents.values()]

    @property
    def total_dashboards(self): return sum(len(s) for s in self.dashboards.values())
    @property
    def total_agents(self): return len(self.agents)
    @property
    def total(self): return self.total_dashboards + self.total_agents

R = Registry()
START = time.time()

async def handle(ws, path=None):
    auth = False; role = uid = None
    try:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await ws.close(4001, "Auth failed"); return
        if msg.get("type") != "auth": await ws.close(4003, "Need auth"); return
        role, uid = msg.get("role",""), msg.get("userId","")
        if not uid: await ws.close(4004, "No userId"); return

        if role == "dashboard":
            await R.register_dashboard(ws, uid); auth = True
            await ws.send(json.dumps({"type":"auth_ok"}))
            await ws.send(json.dumps({"type":"agents_list","agents":R.agents_for(uid)}))
        elif role == "agent":
            await R.register_agent(ws, uid, msg.get("deviceId","unknown")); auth = True
            await ws.send(json.dumps({"type":"auth_ok"}))
        else:
            await ws.close(4005, "Bad role"); return

        async for raw in ws:
            try: msg = json.loads(raw)
            except: continue
            t = msg.get("type","")
            if role == "dashboard":
                if t == "run_tasks":
                    await R.send_to_agents(uid, {"type":"run_tasks","farmId":msg.get("farmId"),"tasks":msg.get("tasks",[]),"from":"dashboard"})
                elif t == "stop_tasks":
                    await R.send_to_agents(uid, {"type":"stop_tasks","farmId":msg.get("farmId"),"from":"dashboard"})
                elif t in ("pause","resume","get_status"):
                    await R.send_to_agents(uid, {"type":t,"from":"dashboard"})
                elif t == "ping":
                    await ws.send(json.dumps({"type":"pong","timestamp":time.time()}))
                elif t == "get_agents":
                    await ws.send(json.dumps({"type":"agents_list","agents":R.agents_for(uid)}))
                else:
                    msg["from"] = "dashboard"; await R.send_to_agents(uid, msg)
            elif role == "agent":
                if t in ("task_status","task_complete","task_error","agent_status","agent_alert","agent_heartbeat","log"):
                    msg["agentId"] = uid; msg["timestamp"] = msg.get("timestamp", time.time())
                    await R._notify_dash(uid, msg)
                elif t == "ping":
                    await ws.send(json.dumps({"type":"pong"}))
                else:
                    msg["agentId"] = uid; await R._notify_dash(uid, msg)
    except websockets.exceptions.ConnectionClosed: pass
    except Exception as e: logger.error(f"Error: {e}")
    finally:
        if auth: await R.unregister(ws)

async def health(path, headers):
    if path in ("/health", "/api/ws/status", "/ws/health"):
        body = json.dumps({"status":"online","version":VERSION,"connections":R.total,"dashboards":R.total_dashboards,"agents":R.total_agents,"agents_list":R.all_agents(),"uptime":time.time()-START})
        return (200, [("Content-Type","application/json"),("Access-Control-Allow-Origin","*")], body.encode())
    return None

async def main(port, use_ssl):
    ssl_ctx = None
    cert = "/etc/letsencrypt/live/ws.vrbot.me/fullchain.pem"
    key = "/etc/letsencrypt/live/ws.vrbot.me/privkey.pem"
    if use_ssl and os.path.exists(cert):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert, key)
        logger.info(f"SSL enabled")
    kw = {"ping_interval":30,"ping_timeout":10,"max_size":1048576,"process_request":health}
    if ssl_ctx: kw["ssl"] = ssl_ctx
    stop = asyncio.Future()
    for s in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(s, stop.set_result, None)
    async with serve(handle, "0.0.0.0", port, **kw):
        p = "wss" if use_ssl else "ws"
        logger.info(f"VRBOT WS Hub v{VERSION} on {p}://0.0.0.0:{port}/ws")
        logger.info(f"Health: http://0.0.0.0:{port}/health")
        await stop
    logger.info("Shut down.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--ssl", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.port, a.ssl))
