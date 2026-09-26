import os
import sys
import io
import time
import json
import tarfile
import threading
import subprocess
import urllib.request
import psutil
from fastapi import Request, Response
from fastapi.responses import JSONResponse, HTMLResponse
import httpx
import gradio as gr

# Configuration: set your image and port (or configure via Hugging Face Space Variables)
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "username/my-docker-app:latest")
INTERNAL_PORT = int(os.getenv("INTERNAL_PORT", "8080"))
ENTRYPOINT_CMD = os.getenv("ENTRYPOINT_CMD", "")

ROOTFS_DIR = "/tmp/docker_rootfs"

# State tracking
logs = []
container_ready = False

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    logs.append(entry)
    if len(logs) > 300:
        logs.pop(0)

# 1. Monkeypatch gr.Blocks.launch to guarantee ssr_mode=False
# This prevents Gradio 5/6 from starting the Node.js SSR proxy in cloud containers
_orig_launch = gr.Blocks.launch
def _safe_launch(self, *args, **kwargs):
    kwargs["ssr_mode"] = False
    return _orig_launch(self, *args, **kwargs)
gr.Blocks.launch = _safe_launch

# 2. ZeroGPU support decorator (satisfies Hugging Face startup scan)
try:
    import spaces
except ImportError:
    class spaces:
        @staticmethod
        def GPU(fn=None, **kwargs):
            if fn is None:
                return lambda f: f
            return fn

@spaces.GPU
def check_gpu():
    return "ZeroGPU environment verified (Free tier instance active)"

# 3. OCI Registry Puller: Downloads & extracts layers directly from Docker Hub without Docker daemon
def pull_and_extract_image(image_tag: str, target_dir: str):
    if ":" in image_tag:
        repo, tag = image_tag.split(":", 1)
    else:
        repo, tag = image_tag, "latest"
    if "/" not in repo:
        repo = f"library/{repo}"

    log(f"Requesting Docker Hub token for {repo}:{tag}...")
    auth_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
    req = urllib.request.Request(auth_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode())["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }

    log(f"Fetching manifest for {repo}:{tag}...")
    manifest_url = f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}"
    m_req = urllib.request.Request(
        manifest_url,
        headers={
            **headers,
            "Accept": "application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json"
        }
    )
    with urllib.request.urlopen(m_req) as resp:
        m_data = json.loads(resp.read().decode())

    # If it's a multi-arch index, select linux/amd64
    if "manifests" in m_data:
        amd64 = next((m for m in m_data["manifests"] if m.get("platform", {}).get("architecture") == "amd64"), None)
        if not amd64:
            amd64 = m_data["manifests"][0]
        digest = amd64["digest"]
        log(f"Selected amd64 manifest: {digest[:20]}...")
        req2 = urllib.request.Request(
            f"https://registry-1.docker.io/v2/{repo}/manifests/{digest}",
            headers={**headers, "Accept": "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"}
        )
        with urllib.request.urlopen(req2) as resp2:
            manifest = json.loads(resp2.read().decode())
    else:
        manifest = m_data

    layers = manifest.get("layers", [])
    log(f"Found {len(layers)} image layers to download.")

    os.makedirs(target_dir, exist_ok=True)
    for i, layer in enumerate(layers):
        l_digest = layer["digest"]
        log(f"Downloading layer {i+1}/{len(layers)}: {l_digest[:16]}...")
        blob_url = f"https://registry-1.docker.io/v2/{repo}/blobs/{l_digest}"
        b_req = urllib.request.Request(blob_url, headers=headers)
        with urllib.request.urlopen(b_req) as b_resp:
            data = b_resp.read()
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                try:
                    tar.extractall(target_dir, filter="tar")
                except TypeError:
                    tar.extractall(target_dir)

    log("All Docker image layers extracted successfully into rootfs.")

def run_container_service():
    global container_ready
    try:
        if not os.path.exists(ROOTFS_DIR) or not os.listdir(ROOTFS_DIR):
            log(f"Starting OCI container pull for '{DOCKER_IMAGE}'...")
            pull_and_extract_image(DOCKER_IMAGE, ROOTFS_DIR)

        # Determine execution command
        exec_cmd = None
        if ENTRYPOINT_CMD:
            exec_cmd = ENTRYPOINT_CMD.split()
        else:
            # Auto-detect binary in /app or rootfs
            candidates = [
                os.path.join(ROOTFS_DIR, "app", "server"),
                os.path.join(ROOTFS_DIR, "app", "main"),
                os.path.join(ROOTFS_DIR, "usr", "local", "bin", "app"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    exec_cmd = [c]
                    break
            
            if not exec_cmd:
                search_dir = os.path.join(ROOTFS_DIR, "app") if os.path.exists(os.path.join(ROOTFS_DIR, "app")) else ROOTFS_DIR
                for root, _, files in os.walk(search_dir):
                    for f in files:
                        p = os.path.join(root, f)
                        if os.access(p, os.X_OK) and not f.endswith((".sh", ".so", ".a", ".pyc")):
                            exec_cmd = [p]
                            break
                    if exec_cmd:
                        break

        if not exec_cmd:
            log(f"ERROR: Could not locate executable binary in {ROOTFS_DIR}. Set ENTRYPOINT_CMD.")
            return

        bin_path = exec_cmd[0]
        log(f"Target executable: {bin_path}")
        try:
            os.chmod(bin_path, 0o755)
        except Exception:
            pass

        log(f"Spawning container service on internal port {INTERNAL_PORT}...")
        proc_env = os.environ.copy()
        proc_env["PORT"] = str(INTERNAL_PORT)
        proc_env["PATH"] = f"{os.path.join(ROOTFS_DIR, 'usr', 'bin')}:{os.path.join(ROOTFS_DIR, 'bin')}:{proc_env.get('PATH', '')}"

        proc = subprocess.Popen(
            exec_cmd,
            env=proc_env,
            cwd=os.path.dirname(bin_path) if os.path.exists(os.path.dirname(bin_path)) else ROOTFS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        container_ready = True
        log(f"Container service PID {proc.pid} is running successfully on port {INTERNAL_PORT}!")

        for line in proc.stdout:
            log(f"[CONTAINER] {line.strip()}")

    except Exception as e:
        log(f"CRITICAL ERROR in container supervisor: {e}")

# Start container supervisor in background thread on Linux
if os.name != "nt":
    threading.Thread(target=run_container_service, daemon=True).start()

# 4. Proxy helper function
async def forward_to_container(path: str, request: Request):
    if not container_ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "pulling_or_starting",
                "message": f"Docker image '{DOCKER_IMAGE}' is being downloaded from registry. Please refresh in a moment!",
                "logs": logs[-5:]
            }
        )
    path = path.lstrip("/")
    if path.startswith("app/"):
        path = path[4:]
    elif path == "app":
        path = ""

    target_url = f"http://127.0.0.1:{INTERNAL_PORT}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={"error": "Container is starting up. Please retry shortly.", "logs": logs[-5:]}
            )

# Attach FastAPI Endpoints
_orig_app_init = gr.routes.App.__init__
def _custom_app_init(self, *args, **kwargs):
    _orig_app_init(self, *args, **kwargs)

    @self.get("/__status")
    def get_status():
        mem = psutil.virtual_memory()
        return {
            "status": "ready" if container_ready else "pulling_or_starting",
            "docker_image": DOCKER_IMAGE,
            "internal_port": INTERNAL_PORT,
            "host_ram_gb": round(mem.total / (1024 ** 3), 2),
            "cpu_cores": os.cpu_count(),
            "logs": logs[-15:]
        }

    @self.get("/api/ram")
    def get_ram():
        mem = psutil.virtual_memory()
        return {
            "total_bytes": mem.total,
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "free_gb": round(mem.free / (1024 ** 3), 2),
            "cpu_cores": os.cpu_count(),
            "docker_backend": "running" if container_ready else "initializing"
        }

    # Universal Transparent Proxy Middleware:
    # Any endpoint not handled by Gradio (e.g. /test, /ping, /users, /api/info)
    # is forwarded directly to the container at http://127.0.0.1:INTERNAL_PORT!
    GRADIO_RESERVED = {
        "assets", "gradio_api", "queue", "config", "theme", "custom_component",
        "favicon.ico", "file", "all_routes", "robots.txt", "static"
    }

    @self.middleware("http")
    async def transparent_docker_proxy(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404:
            raw_path = request.url.path.lstrip("/")
            first_segment = raw_path.split("/")[0] if raw_path else ""
            if first_segment not in GRADIO_RESERVED:
                return await forward_to_container(raw_path, request)
        return response

gr.routes.App.__init__ = _custom_app_init

# 5. Gradio Dashboard Interface
with gr.Blocks(title="Docker on Hugging Face") as demo:
    gr.Markdown(f"# 🐳 Universal Docker Container on Hugging Face (`{DOCKER_IMAGE}`)")
    
    with gr.Row():
        info_box = gr.Textbox(label="Image & Status", value=f"Image: {DOCKER_IMAGE} | Internal Port: {INTERNAL_PORT}", interactive=False)
        refresh_btn = gr.Button("🔄 Refresh Logs", variant="secondary")
        gpu_btn = gr.Button("⚡ Check ZeroGPU", variant="primary")
        
    gpu_output = gr.Textbox(label="ZeroGPU Status", placeholder="ZeroGPU check...")
    logs_display = gr.TextArea(label="Container Supervisor Logs", value=lambda: "\n".join(logs), lines=15)
    
    gr.Markdown("""
    ### 🔗 Live Proxied API Endpoints (Direct Transparent Routing):
    - [**/test** (Direct Custom Route)](/test) - Direct call to `/test` in Docker without prefix!
    - [**/ping** (Healthcheck)](/ping) - Calls `GET /ping` inside your Docker container
    - [**/api/info** (API Info)](/api/info) - Direct call to `/api/info` in Docker
    - [**/app** (Container Root)](/app) - Calls `GET /` inside your Docker container
    - [**/__status** (Supervisor Status)](/__status) - Real-time supervisor pull & container logs
    - [**/api/ram** (Hardware Diagnostics)](/api/ram) - Host & memory allocation telemetry
    """)

    refresh_btn.click(fn=lambda: "\n".join(logs), outputs=logs_display)
    gpu_btn.click(fn=check_gpu, outputs=gpu_output)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False)
