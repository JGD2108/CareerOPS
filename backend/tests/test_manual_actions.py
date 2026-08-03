from types import SimpleNamespace

from app.models import ActionStatus
from app.next_action_agent import _dismiss_stale_actions


def test_manual_actions_are_not_dismissed_as_stale():
    manual = SimpleNamespace(status=ActionStatus.OPEN, completed_at=None)
    generated = SimpleNamespace(status=ActionStatus.OPEN, completed_at=None)

    _dismiss_stale_actions(
        {
            "manual:application-id:action-id": manual,
            "application:follow_up": generated,
        },
        desired_keys=set(),
    )

    assert manual.status == ActionStatus.OPEN
    assert manual.completed_at is None
    assert generated.status == ActionStatus.DISMISSED
    assert generated.completed_at is not None
