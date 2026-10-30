
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Event Workforce API", version="0.1.0")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


def auth_error(exc: Exception) -> HTTPException:
    # Keep provider details out of client responses.
    return HTTPException(status_code=400, detail="Authentication request failed")


def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        # Supabase validates the access token and returns the user.
        response = supabase.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid access token")
        return response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register(payload: RegisterRequest):
    try:
        response = supabase.auth.sign_up({
            "email": str(payload.email),
            "password": payload.password,
            "options": {
                "data": {"full_name": payload.full_name}
            },
        })

        user = response.user
        if not user:
            raise HTTPException(status_code=400, detail="Registration failed")

        return {
            "message": (
                "Registration received. Check your email to confirm your account."
                if not response.session
                else "Registration successful."
            ),
            "user": {
                "id": str(user.id),
                "email": user.email,
            },
            "requires_email_confirmation": response.session is None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise auth_error(exc) from exc


@app.post("/auth/login")
def login(payload: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": str(payload.email),
            "password": payload.password,
        })

        if not response.user or not response.session:
            raise HTTPException(status_code=401, detail="Login failed")

        return {
            "message": "Login successful",
            "user": {
                "id": str(response.user.id),
                "email": response.user.email,
            },
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "expires_in": response.session.expires_in,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise auth_error(exc) from exc


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
    }


@app.post("/auth/logout")
def logout(user=Depends(get_current_user)):
    # Supabase's Python client is shared by the app, so avoid calling
    # global sign_out() here. Client-side token deletion is not enough
    # for server-side revocation. Add a request-scoped auth client if
    # server-side logout/revocation is required.
    return {"message": "Logout endpoint reached", "user_id": str(user.id)}


@app.post("/auth/forgot-password")
def forgot_password(payload: EmailRequest):
    try:
        supabase.auth.reset_password_for_email(str(payload.email))
        # Same response regardless of whether the account exists.
        return {
            "message": "If the account exists, password recovery instructions will be sent."
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not start password recovery"
        ) from exc


@app.post("/auth/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    user=Depends(get_current_user),
):
    # This endpoint requires a valid Supabase access token.
    # The recovery flow must establish a valid recovery session first.
    try:
        supabase.auth.update_user({
            "password": payload.new_password
        })
        return {"message": "Password updated"}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not update password"
        ) from exc
