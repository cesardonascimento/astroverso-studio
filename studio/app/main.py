from fastapi import FastAPI

app = FastAPI(title="Astroverso Studio")


@app.get("/health")
def health() -> dict:
    return {"ok": True}
