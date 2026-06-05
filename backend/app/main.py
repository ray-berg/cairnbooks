from fastapi import FastAPI

app = FastAPI(title="CairnBooks API")


@app.get("/healthz", status_code=200)
def healthz():
    return {"status": "ok"}
