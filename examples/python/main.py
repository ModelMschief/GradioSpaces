import os
import psutil
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Python Microservice inside Docker on Hugging Face")

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "Hello from Python FastAPI Docker Container on Hugging Face!",
        "cpu_count": os.cpu_count(),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "available_ram_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2)
    }

@app.get("/ping")
def ping():
    return {"message": "pong from Python service", "success": True}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
