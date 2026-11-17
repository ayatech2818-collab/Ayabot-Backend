import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from app.models.product import AyabotProduct
from app.models.product_credential import AyabotProductCredential
from app.services.voice_session_service import consume_voice_session_ticket


class ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class ReplayAwareSession:
    def __init__(self) -> None:
        product_id = uuid4()
        credential_id = uuid4()
        self.ticket = SimpleNamespace(
            id=uuid4(),
            product_id=product_id,
            credential_id=credential_id,
        )
        self.credential = SimpleNamespace(
            id=credential_id,
            product_id=product_id,
            is_active=True,
            revoked_at=None,
            expires_at=None,
        )
        self.product = SimpleNamespace(
            id=product_id,
            is_active=True,
        )
        self.consumed = False
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement):
        if self.consumed:
            return ScalarResult(None)
        self.consumed = True
        return ScalarResult(self.ticket.id)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def scalar(self, statement):
        return self.ticket

    def get(self, model, object_id):
        if model is AyabotProductCredential:
            return self.credential
        if model is AyabotProduct:
            return self.product
        raise AssertionError(f"Unexpected model: {model}")


class VoiceSessionTicketTests(unittest.TestCase):
    def test_ticket_can_only_be_consumed_once(self) -> None:
        db = ReplayAwareSession()

        first = consume_voice_session_ticket(db, "one-time-ticket")
        self.assertIs(first, db.ticket)

        with self.assertRaises(HTTPException) as replay:
            consume_voice_session_ticket(db, "one-time-ticket")

        self.assertEqual(replay.exception.status_code, 401)
        self.assertIn("already used", replay.exception.detail)
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.rollbacks, 1)

    def test_oversized_ticket_is_rejected_before_database_access(self) -> None:
        db = ReplayAwareSession()

        with self.assertRaises(HTTPException) as invalid:
            consume_voice_session_ticket(db, "x" * 201)

        self.assertEqual(invalid.exception.status_code, 401)
        self.assertFalse(db.consumed)


if __name__ == "__main__":
    unittest.main()
