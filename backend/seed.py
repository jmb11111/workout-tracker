"""Seed script to create a first user for development/testing."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import engine, SessionLocal, Base
from app.models.user import User, WeightUnit
from app.models import *  # noqa: ensure all models registered


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(User).filter(User.authentik_sub == "seed-admin").first()
        if existing:
            print(f"Seed user already exists: id={existing.id}, name={existing.display_name}")
            return

        user = User(
            authentik_sub="seed-admin",
            display_name="Admin",
            email="admin@localhost",
            weight_unit=WeightUnit.lbs,
            dark_mode=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created seed user: id={user.id}, name={user.display_name}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
