
from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.jobs.router import router as jobs_router
from app.profile.router import router as profile_router
from app.applications.router import router as applications_router
from app.employer_verification.router import router as employer_verification_router
from app.admin.router import router as admin_router

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
app.include_router(profile_router)
app.include_router(applications_router)
app.include_router(employer_verification_router)
app.include_router(admin_router)
