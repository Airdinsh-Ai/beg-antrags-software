import uuid
from collections.abc import Callable

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import authenticate_user, create_access_token, decode_access_token
from app.models.user import User, UserRole
from app.schemas.auth import CurrentUserOut, LoginRequest, TokenResponse

# HTTPBearer statt OAuth2PasswordBearer: Phase 0 verlangt JSON-Requests
# (Systemarchitektur Abschnitt 2.5), kein Form-Login.
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungueltiges oder abgelaufenes Token"
        ) from exc

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungueltiges Token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nutzer nicht gefunden")
    return user


def require_role(*roles: UserRole) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nicht berechtigt")
        return user

    return dependency


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login fehlgeschlagen")
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)) -> None:
    # Zustandsloses JWT ohne Blocklist-Tabelle: dokumentierter No-Op, das Token
    # bleibt bis zum Ablauf gueltig. Echte Invalidierung ist ein Backlog-Punkt
    # fuer Phase 1/2 (keine Session-Tabelle im vorgegebenen Datenmodell).
    return None


@router.get("/me", response_model=CurrentUserOut)
def me(current_user: User = Depends(get_current_user)) -> CurrentUserOut:
    return CurrentUserOut.model_validate(current_user)
