# Python FastAPI Docker Starter for Hugging Face

A fast, lightweight FastAPI REST API container running on internal port `8080`.

## Build and Push to Docker Hub

```bash
docker build -t your-username/hf-python-api:latest .
docker push your-username/hf-python-api:latest
```

## Configuration in `hf-template/app.py`

In `app.py`:
```python
DOCKER_IMAGE = "your-username/hf-python-api:latest"
INTERNAL_PORT = 8080
ENTRYPOINT_CMD = "python /app/main.py"
```
