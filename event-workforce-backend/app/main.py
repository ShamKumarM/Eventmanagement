from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.errors import request_validation_exception_handler
from app.auth.router import router as auth_router
from app.jobs.router import router as jobs_router
from app.profile.router import router as profile_router
from app.applications.router import router as applications_router
from app.employer_verification.router import router as employer_verification_router
from app.admin.router import router as admin_router
from app.recommendations.router import router as recommendations_router
from app.socialism.router import router as socialism_router, legacy_router as socialism_legacy_router

app = FastAPI(
    title="Coimbatore Event Workforce Platform API",
    description="Backend API for workers, employers, and event management.",
    version="1.3.0",
)

app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,
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
app.include_router(recommendations_router)
app.include_router(socialism_router)
app.include_router(socialism_legacy_router)
