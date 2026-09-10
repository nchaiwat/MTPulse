from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.api.automatic_imports import router as automatic_imports_router
from app.api.dashboards import router as dashboards_router
from app.api.data_coverage import router as data_coverage_router
from app.api.fileshare_settings import router as fileshare_settings_router
from app.api.import_correctives import router as import_correctives_router
from app.api.imports import router as imports_router
from app.api.item_mappings import router as item_mappings_router
from app.api.manual_uploads import router as manual_uploads_router
from app.api.monitoring import router as monitoring_router
from app.api.performance import router as performance_router
from app.api.sku_analysis_flags import router as sku_analysis_flags_router
from app.api.sku_interests import router as sku_interests_router
from app.api.system_settings import router as system_settings_router
from app.api.twd_settings import modern_trade_router
from app.api.twd_settings import router as twd_settings_router
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
app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)
app.include_router(data_coverage_router)
app.include_router(automatic_imports_router)
app.include_router(dashboards_router)
app.include_router(performance_router)
app.include_router(item_mappings_router)
app.include_router(imports_router)
app.include_router(manual_uploads_router)
app.include_router(import_correctives_router)
app.include_router(system_settings_router)
app.include_router(twd_settings_router)
app.include_router(modern_trade_router)
app.include_router(fileshare_settings_router)
app.include_router(sku_interests_router)
app.include_router(sku_analysis_flags_router)
app.include_router(monitoring_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
