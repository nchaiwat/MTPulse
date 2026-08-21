from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.item_mappings import router as item_mappings_router
from app.api.performance import router as performance_router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(performance_router)
app.include_router(item_mappings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
