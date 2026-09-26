# 🚀 GradioSpaces: Run Any Docker Container Free on Hugging Face

[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-yellow)](https://huggingface.co/spaces)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![ZeroGPU Compatible](https://img.shields.io/badge/ZeroGPU-Compatible-green)](https://huggingface.co/docs/hub/spaces-gpus)
[![Docker](https://img.shields.io/badge/Docker-No%20Daemon%20Required-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

> **Deploy and run ANY Docker container (Go, Node.js, Python, Rust, C++, etc.) completely FREE on Hugging Face Spaces using the ZeroGPU free tier with 16 GB+ RAM.**

---

## 💡 The Problem & The Discovery

### 1. The Paywall
Hugging Face recently restricted standalone Docker Spaces (`sdk: docker`) to paid PRO subscriptions ($9/mo+). Attempting to deploy or downgrade Docker Spaces to free tiers fails with `402 Payment Required`.

### 2. The Free Tier Loophole
While Docker Spaces are paid, **Gradio Spaces with ZeroGPU (`zero-a10g`) remain 100% FREE**. 
Even better: they are hosted on enterprise supercomputer nodes with **16 GB to 2,000 GB host memory pools** and up to **192 vCPUs**.

### 3. The Challenge
Hugging Face free containers are unprivileged Kubernetes pods:
* ❌ No Docker daemon (`dockerd`) running.
* ❌ No `/var/run/docker.sock`.
* ❌ No root/sudo privileges.
* ❌ ZeroGPU supervisor crashes containers that lack an `@spaces.GPU` decorator.
* ❌ Only port `7860` is exposed to the public internet.

---

## ⚡ The Solution: Universal OCI Container Runner

This repository provides an automated, self-contained Python supervisor (`hf-template/app.py`) that runs inside the free Gradio tier:

```
[Incoming Public Traffic: https://your-space.hf.space]
                           │
                     (Port 7860)
                           ▼
┌────────────────────────────────────────────────────────┐
│ Hugging Face Free Tier Container (Python / Gradio)     │
│                                                        │
│  1. ZeroGPU Validator: Dummy @spaces.GPU satisfies HF  │
│  2. OCI Registry Puller: Downloads Docker image layers │
│  3. Extractor: Unpacks image to /tmp/docker_rootfs     │
│  4. Process Runner: Spawns container binary in /tmp    │
│  5. Reverse Proxy: Bridges Port 7860 -> Port 8080      │
└────────────────────────────────────────────────────────┘
                           │
                  (Internal Loopback)
                           ▼
  [Your Containerized Service listening on 127.0.0.1:8080]
```

1. **Zero Daemon Needed:** Talks directly to Docker Hub's v2 OCI HTTP API, downloads the compressed layer blobs, and extracts them natively with Python.
2. **ZeroGPU Bypassed:** Includes a dummy `@spaces.GPU` function so Hugging Face provisions the free 16 GB+ instance.
3. **Transparent Reverse Proxy:** Forwards all incoming HTTP traffic from port `7860` directly to your container running on internal port `8080`.
4. **Language Agnostic:** Works with any language or runtime that can be containerized.

---

## 📁 Repository Structure

```
gradiospaces/
├── README.md                      # Documentation & Guide (You are here)
├── LICENSE                        # MIT License
├── hf-template/                   # Universal Hugging Face Deployment Template
│   ├── app.py                     # Universal OCI container puller & FastAPI reverse proxy
│   ├── requirements.txt           # Minimal dependencies
│   └── README.md                  # Hugging Face Space metadata header (sdk: gradio)
└── examples/                      # Language-specific Docker starter kits
    ├── golang/                    # Verified Go REST API container
    │   ├── main.go
    │   ├── go.mod
    │   ├── Dockerfile
    │   └── .dockerignore
    ├── nodejs/                    # Express.js REST API container
    │   ├── server.js
    │   ├── package.json
    │   ├── Dockerfile
    │   └── .dockerignore
    └── python/                    # Standalone FastAPI container
        ├── main.py
        ├── requirements.txt
        ├── Dockerfile
        └── .dockerignore
```

---

## 🚀 Quickstart Guide (Deploy in 3 Steps)

### Step 1: Build & Push Your Docker Image
Build your container image for `linux/amd64` and push it to Docker Hub (make sure the repository is **public**):

```bash
cd examples/golang   # Or nodejs / python
docker build -t your-username/my-service:latest .
docker push your-username/my-service:latest
```
*(Ensure your service inside the container listens on port `8080`)*

### Step 2: Create a Free Hugging Face Space
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Choose a name (e.g., `my-service`).
3. Select **Gradio** as the Space SDK (do NOT select Docker).
4. Leave the hardware tier as **ZeroGPU (free)**.

### Step 3: Copy & Deploy the Universal Template
1. Clone your new Hugging Face Space repository locally:
   ```bash
   git clone https://huggingface.co/spaces/your-username/my-service
   cd my-service
   ```
2. Copy the files from [`hf-template/`](hf-template/):
   - `app.py`
   - `requirements.txt`
   - `README.md`
3. In `app.py`, set your Docker image name:
   ```python
   DOCKER_IMAGE = "your-username/my-service:latest"
   ```
4. Commit and push:
   ```bash
   git add .
   git commit -m "Deploy container via Universal OCI Runner"
   git push origin main
   ```

Within ~30 seconds, your Hugging Face Space will download the image layers, launch your container, and start serving public traffic!

---

## 🔗 Live Verification & Telemetry

You can verify the live deployment running on Hugging Face:

| Endpoint | Purpose | Live Output |
| :--- | :--- | :--- |
| `GET /` | Root application endpoint | Proxied directly from the Docker container |
| `GET /ping` | Healthcheck endpoint | `{"message": "pong", "success": true}` |
| `GET /__status` | Supervisor & pull logs | Full OCI download logs & memory stats |
| `GET /api/ram` | Hardware diagnostics | Reports container allocation & host hardware |

---

## ⏰ Keeping the Free Tier Alive (24/7 Uptime)

Hugging Face free Spaces enter sleep mode after **48 hours** (`172,800 seconds`) of inactivity.

To keep your service running **24/7 forever**:
1. Create a free account on [UptimeRobot](https://uptimerobot.com) or [Cron-job.org](https://cron-job.org).
2. Set up an **HTTP(s) Monitor** pointing to your Space URL:
   `https://your-space-name.hf.space/ping`
3. Set the interval to **every 5 to 15 minutes**.
4. Every ping resets the 48-hour idle countdown timer back to zero!

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
