from __future__ import annotations

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Action, ActionStatus, ActionType


def run() -> None:
    db = SessionLocal()
    try:
        total = db.scalar(
            select(func.count(Action.id)).where(
                Action.status == ActionStatus.OPEN,
                Action.action_type == ActionType.SEND_FOLLOW_UP,
            )
        )
        missing = db.scalar(
            select(func.count(Action.id)).where(
                Action.status == ActionStatus.OPEN,
                Action.action_type == ActionType.SEND_FOLLOW_UP,
                Action.email_id.is_(None),
            )
        )
        print({"open_send_follow_up": int(total or 0), "missing_email_id": int(missing or 0)})
    finally:
        db.close()


if __name__ == "__main__":
    run()
