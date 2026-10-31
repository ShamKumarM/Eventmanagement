
from fastapi import FastAPI

from app.routes.auth import router as auth_router
from app.jobs.router import router as jobs_router

app = FastAPI(
    title="Coimbatore Event Workforce Platform API",
    description="Backend API for workers, employers, and event management.",
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(jobs_router)
