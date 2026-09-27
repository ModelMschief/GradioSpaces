# 📜 Hugging Face Spaces: Deployment Rules & Safety Guidelines

To prevent your Hugging Face Space from being paused, flagged as abusive, or locked out by automated Trust & Safety heuristics, follow these essential operational rules.

---

## 1. 🚫 Never Download External Sandboxing/Evasion Binaries at Runtime

- **The Rule:** Do **NOT** download user-space jailbreaking tools, chroot shims, or binaries like `proot` from external URLs (e.g. `gitlab.io`, GitHub releases) during container startup.
- **Why It Matters:** Hugging Face monitors network egress and process execution during Space boot. Automated heuristic bots actively look for patterns associated with cryptominers or container sandbox escapes. Pulling external binaries and executing them with `chmod +x` will instantly trip automated flags (`"Flagged as abusive"`).
- **The Solution:** Keep your Docker image completely self-contained. All binaries, compilers, and shared libraries (`.so`, `.dll`) must be baked directly into your Docker image on Docker Hub or GHCR before deploying.

---

## 2. 🔒 Public vs. Private Spaces & The Frontend / Browser API Limitation

Understanding the difference between Public and Private Spaces is critical for API design:

| Feature | Public Space 🌐 | Private Space 🔒 |
| :--- | :--- | :--- |
| **Authentication** | None required (open endpoints) | Requires `Authorization: Bearer <HF_TOKEN>` |
| **Edge Traffic Inspection** | Active (Cloudflare / HF WAF) | Bypassed (Private sandbox) |
| **Frontend / Browser Access** | ✅ Works directly via `fetch()` | ❌ **Cannot be called directly from browsers** |
| **Best For** | Public APIs, web apps, standard AI | Backend microservices, private testing |

### ⚠️ The Critical Frontend / Browser Limitation on Private Spaces

When a Space is set to **Private**:
1. **Secret Exposure Hazard:** Every HTTP request requires a Hugging Face Bearer token. Calling a Private Space directly from client-side JavaScript (React, Vue, Next.js, mobile apps, or vanilla browser `fetch`) would require embedding your secret Hugging Face token in frontend code, exposing it to anyone who inspects network traffic.
2. **CORS & Preflight Failures:** Browser cross-origin preflight requests (`OPTIONS`) do not carry Bearer credentials, which often causes the Hugging Face gateway to reject the request before it even reaches your container.

> **💡 The Architecture Rule:**
> - If your API must be accessed **directly from browser frontends**, the Space **must be Public**. You must strictly avoid any content that violates Hugging Face's public Terms of Service (no un-gated adult/NSFW content).
> - If your Space is **Private**, requests should **only be made from a secure backend server** (e.g. a Node.js, Go, or Python backend, or Next.js server route) that securely holds the `HF_TOKEN` in its environment variables and proxies calls to the Space.

---

## 3. 🔞 Content Safety on Public Spaces

- **Public Spaces:** Never send or host un-gated explicit adult material (NSFW, pornography) on a Public Space. Automated edge inspection will flag the Space and lock the account.
- **Content Moderation Testing:** If you are developing or testing content moderation filters, safety classifiers, or adult-content detection models, the Space **must be Private**.

---

## 4. 📦 Keep Shared Libraries Local to `/app`

- If your application uses native C/C++ shared libraries (e.g. Microsoft ONNX Runtime `libonnxruntime.so`, OpenCV, or FFmpeg), place the `.so` files directly inside `/app` right next to your binary.
- This ensures your application loads its dependencies locally from its working directory without needing system-level library hacks or root privileges.

---

## 5. 💾 Temporary (Ephemeral) Disk Storage

- Free Spaces provide **50 GB of ephemeral disk storage** in `/tmp`.
- Files stored on this disk will be reset if the Space restarts or rebuilds.
- For persistent data (user accounts, uploads, databases), always connect your application to an external cloud database (Supabase, Neon, MongoDB Atlas) or object storage (AWS S3, Cloudflare R2).

---

## 6. ⏰ Prevent Inactivity Sleep with Keepalive Pings

- Free Spaces automatically enter sleep mode after a period of inactivity.
- Set up a free monitoring service (e.g. [UptimeRobot](https://uptimerobot.com) or [Better Stack](https://betterstack.com)) to ping your Space's `/ping` or health endpoint every 5 to 10 minutes to maintain persistent 24/7 uptime.
