from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.workouts import router as workouts_router
from app.api.results import router as results_router
from app.api.movements import router as movements_router
from app.api.records import router as records_router
from app.api.users import router as users_router
from app.api.scraper_api import router as scraper_router
from app.api.admin import router as admin_router
from app.api.auth_routes import router as auth_router
from app.scraper.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Workout Tracker",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(workouts_router, prefix="/api/workouts", tags=["workouts"])
app.include_router(results_router, prefix="/api/results", tags=["results"])
app.include_router(movements_router, prefix="/api/movements", tags=["movements"])
app.include_router(records_router, prefix="/api/records", tags=["records"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(scraper_router, prefix="/api/scraper", tags=["scraper"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
