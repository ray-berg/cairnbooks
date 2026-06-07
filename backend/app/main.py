from fastapi import FastAPI

app = FastAPI(
    title="CairnBooks API",
    description="Open-source double-entry accounting platform for small businesses.",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "cairnbooks-api"}
