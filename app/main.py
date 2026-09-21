from fastapi import FastAPI

from app.core.auth import router as auth_router
from app.modules.funding.routes import router as funding_router
from app.modules.measures.routes import router as measures_router
from app.modules.property.routes import router as property_router

app = FastAPI(title="BEG-Antrags-Software")

app.include_router(auth_router)
app.include_router(property_router)
app.include_router(funding_router)
app.include_router(measures_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
