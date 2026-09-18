"""Legt idempotent einen Demo-Berater-Nutzer an.

Phase 0 sieht laut Systemarchitektur (Abschnitt 11) keinen Registrierungs-Endpoint
vor - dieses Skript ist der einzige Weg, den allerersten Nutzer fuer den manuellen
Postman-Test anzulegen, ohne von der dokumentierten Endpunktliste abzuweichen.

Aufruf: uv run python -m scripts.seed_demo_data
"""

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole

DEMO_EMAIL = "berater@example.com"
DEMO_PASSWORD = "demo-passwort-123"


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if existing is not None:
            print(f"Demo-Nutzer existiert bereits: {DEMO_EMAIL}")
            return

        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.BERATER,
        )
        db.add(user)
        db.commit()
        print(f"Demo-Nutzer angelegt: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
