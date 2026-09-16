from fastapi import FastAPI

app = FastAPI(title="BEG-Antrags-Software")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
