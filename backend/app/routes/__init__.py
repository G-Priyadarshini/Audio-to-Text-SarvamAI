from fastapi import APIRouter
from app.routes.jobs import router as jobs_router
from app.routes.uploads import router as uploads_router
from app.routes.transcripts import router as transcripts_router
from app.routes.stream import router as stream_router
from app.routes.compat import router as compat_router
from app.routes.sarvam_jobs import router as sarvam_jobs_router
from app.routes.settings import router as settings_router

api_router = APIRouter(prefix="/api")
api_router.include_router(jobs_router)
api_router.include_router(uploads_router)
api_router.include_router(transcripts_router)
api_router.include_router(stream_router)
api_router.include_router(compat_router)
api_router.include_router(sarvam_jobs_router)
api_router.include_router(settings_router)
