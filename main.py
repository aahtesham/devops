"""Placeholder app so the first cloud deploy succeeds. Crypto analysis comes next."""

from fastapi import FastAPI

app = FastAPI(title="Crypto Analysis", version="0.0.1")


@app.get("/")
def health():
    return {"status": "ok", "message": "Replace this with analysis endpoints when ready."}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
