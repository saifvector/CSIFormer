from fastapi import APIRouter
from app.api.endpoints import system, csi, localization, datasets, spatial, hardware

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(csi.router)
api_router.include_router(localization.router)
api_router.include_router(datasets.router)
api_router.include_router(spatial.router)
api_router.include_router(hardware.router)
