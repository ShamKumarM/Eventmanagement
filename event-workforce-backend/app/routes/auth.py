import logging
import re
from html import escape

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse

from app.core.config import RECOVERY_REDIRECT_URL
from app.schemas.auth import (
    CompletePasswordResetRequest,
    EmailRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.supabase_client import create_supabase_client, supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _log_auth_error(action: str, exc: Exception) -> None:
    """Log useful diagnostics locally without returning secrets to API clients."""
    logger.exception("%s failed (%s)", action, type(exc).__name__)
    for attribute in ("message", "status", "code", "details", "hint"):
        value = getattr(exc, attribute, None)
        if value:
            logger.error("Supabase %s: %s", attribute, value)


def _public_auth_error(exc: Exception) -> tuple[int, str]:
    """Map common Supabase Auth errors to safe, user-facing responses."""
    message = str(exc).lower()

    if "email rate limit exceeded" in message or "rate limit" in message:
        return 429, "Email rate limit reached. Wait before trying again."
    if "invalid login credentials" in message:
        return 401, "Invalid email or password."
    if "email not confirmed" in message:
        return 401, "Please confirm your email before logging in."
    if "already registered" in message or "already been registered" in message:
        return 409, "An account with this email may already exist."
    if "password" in message and ("weak" in message or "short" in message):
        return 400, "The password does not meet the requirements."
    return 400, "The authentication request could not be completed. Check the server logs."


def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide an Authorization: Bearer <access_token> header.",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token.")

    try:
        response = create_supabase_client().auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired session.")
        return response.user
    except HTTPException:
        raise
    except Exception as exc:
        _log_auth_error("Token verification", exc)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        ) from exc


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    try:
        response = supabase.auth.sign_up(
            {
                "email": str(payload.email),
                "password": payload.password,
                "options": {"data": {"full_name": payload.full_name}},
            }
        )

        user = response.user
        if not user:
            raise HTTPException(
                status_code=400,
                detail="Registration could not be completed.",
            )

        return {
            "message": (
                "Registration successful. Check your email to confirm your account."
                if response.session is None
                else "Registration successful."
            ),
            "user": {"id": str(user.id), "email": user.email},
            "requires_email_confirmation": response.session is None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        _log_auth_error("Registration", exc)
        http_status, message = _public_auth_error(exc)
        raise HTTPException(status_code=http_status, detail=message) from exc


@router.post("/login")
def login(payload: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password(
            {"email": str(payload.email), "password": payload.password}
        )

        if not response.user or not response.session:
            raise HTTPException(
                status_code=401,
                detail="Login failed. Check your credentials and email confirmation.",
            )

        return {
            "message": "Login successful.",
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
        _log_auth_error("Login", exc)
        http_status, message = _public_auth_error(exc)
        raise HTTPException(status_code=http_status, detail=message) from exc


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email}


@router.post("/refresh")
def refresh_session(payload: RefreshRequest):
    try:
        response = create_supabase_client().auth.refresh_session(
            payload.refresh_token
        )
        if not response.session:
            raise HTTPException(
                status_code=401,
                detail="Refresh token is invalid or expired.",
            )

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "expires_in": response.session.expires_in,
        }
    except HTTPException:
        raise
    except Exception as exc:
        _log_auth_error("Session refresh", exc)
        raise HTTPException(
            status_code=401,
            detail="Refresh token is invalid or expired.",
        ) from exc


@router.post("/logout")
def logout(user=Depends(get_current_user)):
    # This endpoint validates the access token but does not revoke the Supabase
    # session because the request-scoped client is not authenticated as that user.
    # The client must discard its tokens. Implement server-side revocation before
    # treating this endpoint as a complete logout mechanism.
    return {
        "message": "Logout acknowledged. Clear stored tokens on the client.",
        "user_id": str(user.id),
    }


@router.post("/forgot-password")
def forgot_password(payload: EmailRequest):
    try:
        supabase.auth.reset_password_for_email(
            str(payload.email),
            options={"redirect_to": RECOVERY_REDIRECT_URL},
        )
        # Same response regardless of whether the account exists.
        return {
            "message": "If the account exists, password recovery instructions will be sent."
        }
    except Exception as exc:
        _log_auth_error("Password recovery request", exc)
        message = str(exc).lower()
        if "email rate limit exceeded" in message or "rate limit" in message:
            raise HTTPException(
                status_code=429,
                detail="Supabase email rate limit reached. Wait before trying again.",
            ) from exc
        raise HTTPException(
            status_code=400,
            detail="Could not start password recovery. Check server configuration and logs.",
        ) from exc


@router.get("/recovery/callback", response_class=HTMLResponse)
def recovery_page():
    # Supabase commonly returns recovery tokens in the URL fragment. Fragments
    # are not sent to the server, so this page reads them in the browser.
    html = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reset Password | Event Workforce</title>
<style>
body{font-family:Arial,sans-serif;background:#f3f4f6;margin:0;min-height:100vh;display:grid;place-items:center;color:#111827}
.card{background:#fff;padding:30px;border-radius:16px;width:min(400px,85%);box-shadow:0 10px 35px #0001}
h1{font-size:25px;margin-top:0}
label{display:block;margin-top:16px;font-weight:600}
input{box-sizing:border-box;width:100%;padding:12px;margin-top:7px;border:1px solid #d1d5db;border-radius:8px}
ul{padding-left:22px;line-height:1.8}
button{width:100%;margin-top:22px;padding:13px;border:0;border-radius:8px;background:#2563eb;color:white;font-weight:bold;cursor:pointer}
button:disabled{opacity:.6;cursor:not-allowed}
#message{white-space:pre-wrap;line-height:1.5}
.error{color:#dc2626}.success{color:#15803d}
</style>
</head>
<body>
<main class="card">
<h1>Reset your password</h1>
<p>Choose a strong new password for your account.</p>
<form id="reset-form">
<label for="password">New password</label>
<input id="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required>
<ul>
<li id="length">At least 8 characters</li>
<li id="upper">One uppercase letter (A-Z)</li>
<li id="lower">One lowercase letter (a-z)</li>
<li id="number">One number (0-9)</li>
<li id="symbol">One special symbol</li>
</ul>
<label for="confirm">Confirm new password</label>
<input id="confirm" type="password" minlength="8" maxlength="128" autocomplete="new-password" required>
<button id="submit" type="submit">Update password</button>
<p id="message" role="status"></p>
</form>
</main>
<script>
const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirm");
const submitButton = document.getElementById("submit");
const message = document.getElementById("message");
const rules = [
  ["length", p => p.length >= 8],
  ["upper", p => /[A-Z]/.test(p)],
  ["lower", p => /[a-z]/.test(p)],
  ["number", p => /[0-9]/.test(p)],
  ["symbol", p => /[^A-Za-z0-9]/.test(p)]
];
function validateStrength() {
  const p = password.value;
  for (const [id, check] of rules) {
    document.getElementById(id).style.color = check(p) ? "#15803d" : "#6b7280";
  }
}
password.addEventListener("input", validateStrength);

const params = new URLSearchParams(window.location.hash.slice(1));
const accessToken = params.get("access_token");
const refreshToken = params.get("refresh_token");
const recoveryType = params.get("type");
const hashError = params.get("error_description");

if (hashError) {
  message.textContent = "Recovery link error: " + hashError.replace(/\+/g, " ");
  message.className = "error";
} else if (!accessToken || !refreshToken || recoveryType !== "recovery") {
  message.textContent = "This recovery link is invalid, expired, or missing its recovery session. Request a fresh password-reset email.";
  message.className = "error";
} else {
  // Keep tokens in page memory and remove the fragment from the address bar.
  history.replaceState(null, "", window.location.pathname);
}

document.getElementById("reset-form").addEventListener("submit", async event => {
  event.preventDefault();
  message.textContent = "";
  message.className = "";

  if (!accessToken || !refreshToken || recoveryType !== "recovery") {
    message.textContent = "Recovery session is invalid or expired. Request a fresh email.";
    message.className = "error";
    return;
  }
  if (!rules.every(([, check]) => check(password.value))) {
    message.textContent = "Please meet all password requirements.";
    message.className = "error";
    return;
  }
  if (password.value !== confirmPassword.value) {
    message.textContent = "Passwords do not match.";
    message.className = "error";
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Updating...";
  try {
    const response = await fetch("/auth/reset-password", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        access_token: accessToken,
        refresh_token: refreshToken,
        new_password: password.value
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Password update failed.");
    password.value = "";
    confirmPassword.value = "";
    message.textContent = "Password updated successfully. You can now log in with your new password.";
    message.className = "success";
  } catch (error) {
    message.textContent = error.message || "Password update failed. Request a fresh recovery email.";
    message.className = "error";
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Update password";
  }
});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/reset-password")
def reset_password(payload: CompletePasswordResetRequest):
    client = create_supabase_client()
    try:
        # Establish the supplied Supabase session in this request-scoped client.
        client.auth.set_session(payload.access_token, payload.refresh_token)

        current = client.auth.get_user(payload.access_token)
        if not current.user:
            raise HTTPException(
                status_code=401,
                detail="Recovery session is invalid or expired. Request a fresh email.",
            )

        client.auth.update_user({"password": payload.new_password})
        return {"message": "Password updated successfully."}
    except HTTPException:
        raise
    except Exception as exc:
        _log_auth_error("Password update", exc)
        raise HTTPException(
            status_code=400,
            detail=(
                "Recovery session is invalid or expired, or the password update failed. "
                "Request a fresh email."
            ),
        ) from exc
