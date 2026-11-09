
from fastapi import FastAPI

app = FastAPI(
    title="Agentic AI POC",
    description="My local Agentic AI development environment",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to Agentic AI POC",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.get("/test")
async def test():
    return "Hello"
