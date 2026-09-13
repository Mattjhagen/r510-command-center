import os, time, socket, platform, subprocess, pathlib
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HTML = pathlib.Path(__file__).parent / "r510.html"

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(HTML.read_text() if HTML.exists() else "<h1>r510.html missing</h1>")

@app.get("/api/tty")
async def tty():
    import psutil
    out = {}
    try: out["cpu"] = psutil.cpu_percent(interval=0.1)
    except: out["cpu"] = 0
    try:
        m = psutil.virtual_memory()
        out["mem_pct"]=round(m.percent,1); out["mem_used"]=round(m.used/1e9,1)
        out["mem_total"]=round(m.total/1e9,1); out["mem_free"]=round(m.available/1e9,1)
    except: pass
    try:
        d = psutil.disk_usage("/")
        out["disk_pct"]=round(d.percent,1); out["disk_free"]=round(d.free/1e9,1)
    except: pass
    try:
        sw = psutil.swap_memory()
        out["swap_pct"]=round(sw.percent,1)
    except: pass
    try:
        temps = psutil.sensors_temperatures()
        for k in ["coretemp","k10temp","acpitz"]:
            if k in temps and temps[k]:
                out["temp"]=round(temps[k][0].current,1); break
    except: pass
    try:
        boot=psutil.boot_time(); up=time.time()-boot
        d2,h,mi=int(up//86400),int((up%86400)//3600),int((up%3600)//60)
        out["uptime"]=f"{d2}d {h}h {mi}m" if d2 else (f"{h}h {mi}m" if h else f"{mi}m")
    except: pass
    try:
        la=os.getloadavg()
        out["load_avg"]=f"{la[0]:.2f} {la[1]:.2f} {la[2]:.2f}"
    except: pass
    try: out["proc_count"]=len(psutil.pids())
    except: pass
    try: out["hostname"]=socket.gethostname()
    except: pass
    try: out["kernel"]=platform.release()
    except: pass
    try: out["cpu_count"]=psutil.cpu_count()
    except: pass
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    out["cpu_model"]=line.split(":")[1].strip(); break
    except: pass
    try:
        r=subprocess.run(["tailscale","ip","-4"],capture_output=True,text=True,timeout=2)
        if r.returncode==0: out["tailscale_ip"]=r.stdout.strip()
    except: pass
    try:
        users=[{"name":u.name,"terminal":u.terminal or "?","host":u.host or "local","started":time.strftime("%H:%M %m/%d",time.localtime(u.started))} for u in psutil.users()]
        out["users"]=users; out["user_count"]=len(users)
    except: pass
    try:
        procs=[]
        for p in psutil.process_iter(["pid","name","username","cpu_percent","memory_percent","memory_info"]):
            try:
                i=p.info
                procs.append({"pid":i["pid"],"name":i["name"],"user":i.get("username","?") or "?",
                    "cpu":round(i.get("cpu_percent") or 0,1),"mem":round(i.get("memory_percent") or 0,1),
                    "mem_mb":round((i.get("memory_info") and i["memory_info"].rss or 0)/1e6)})
            except: pass
        procs.sort(key=lambda x:x["cpu"],reverse=True)
        out["procs"]=procs[:12]
    except: pass
    try:
        addrs=psutil.net_if_addrs(); io1=psutil.net_io_counters(pernic=True)
        time.sleep(0.2); io2=psutil.net_io_counters(pernic=True)
        net={}
        for iface,al in addrs.items():
            if iface=="lo": continue
            ip=next((a.address for a in al if a.family==2),None)
            if not ip: continue
            i1=io1.get(iface); i2=io2.get(iface)
            net[iface]={"ip":ip,
                "rx_sec":int((i2.bytes_recv-i1.bytes_recv)/0.2) if i1 and i2 else 0,
                "tx_sec":int((i2.bytes_sent-i1.bytes_sent)/0.2) if i1 and i2 else 0,
                "rx_total":i2.bytes_recv if i2 else 0,"tx_total":i2.bytes_sent if i2 else 0}
        out["net"]=net
    except: pass
    try:
        conns=psutil.net_connections()
        out["connections"]=len([c for c in conns if c.status=="ESTABLISHED"])
        ports=sorted(set(c.laddr.port for c in conns if c.status=="LISTEN" and c.laddr))
        out["listening_ports"]=" ".join(map(str,ports[:8]))
    except: pass
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=1)
        if r.status_code == 200:
            data = r.json()
            out["ollama_online"] = True
            if data.get("models"):
                out["ollama_model"] = data["models"][0]["name"]
        else:
            out["ollama_online"] = False
    except:
        out["ollama_online"] = False
    return out

import asyncio, pty, os, select, termios, struct, fcntl


@app.get("/api/training")
async def training_status():
    """Get current training status"""
    import os, re
    log_path = os.path.expanduser("~/train_nightly.log")

    if not os.path.exists(log_path):
        return {"running": False, "recent_steps": []}

    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-100:]

        steps = []
        for line in lines:
            match = re.search(r"step\s+(\d+)\s+loss\s+([\d.]+)", line)
            if match:
                steps.append({
                    "step": int(match.group(1)),
                    "loss": float(match.group(2))
                })

        recent = steps[-10:] if steps else []
        return {"running": len(steps) > 0, "recent_steps": recent}
    except:
        return {"running": False, "recent_steps": []}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7072))
    print(f"\n  R510 Command Center → http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
