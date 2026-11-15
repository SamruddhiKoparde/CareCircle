
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.config import APP_NAME, BASE_DIR
from backend.app.database import init_db, get_db
from backend.app.auth import require_permission

from backend.app.routes import router as auth_router
from backend.app.medication_routes import router as medication_router
from backend.app.appointment_routes import router as appointment_router

from backend.app.services.dashboard_service import get_dashboard_data

from backend.app.services.scheduler_service import (
    scheduler,
    start_scheduler,
    stop_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()

    yield

    stop_scheduler()


app = FastAPI(
    title=APP_NAME,
    description="Patient-controlled elderly care and medication management.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve frontend CSS and JavaScript.
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

# Register API routes.
app.include_router(auth_router)
app.include_router(medication_router)
app.include_router(appointment_router)


@app.get("/api/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_view_profile")),
):
    dashboard_data = get_dashboard_data(
        patient_id=current_user["patient_id"],
        db=db,
    )

    if dashboard_data is None:
        raise HTTPException(
            status_code=404,
            detail="Patient dashboard not found.",
        )

    return dashboard_data


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": APP_NAME,
        "scheduler_running": scheduler.running,
        "scheduled_jobs": len(scheduler.get_jobs()),
    }


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "templates" / "index.html")
