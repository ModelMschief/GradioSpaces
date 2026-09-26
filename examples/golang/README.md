# Golang Docker Starter for Hugging Face

A fast, lightweight Go REST API container that compiles to a statically linked binary and runs on internal port `8080`.

## Build and Push to Docker Hub

```bash
docker build -t your-username/hf-go-api:latest .
docker push your-username/hf-go-api:latest
```

## Configuration in `hf-template/app.py`

In `app.py`:
```python
DOCKER_IMAGE = "your-username/hf-go-api:latest"
INTERNAL_PORT = 8080
```
