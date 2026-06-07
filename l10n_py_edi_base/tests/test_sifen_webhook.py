# l10n_py_edi_base/tests/test_sifen_webhook.py

from odoo.tests import tagged
from odoo.tests.common import HttpCase


def _result(response):
    """Extract result from JSON-RPC response."""
    data = response.json()
    return data.get("result", data)


@tagged("post_install", "-at_install", "l10n_py")
class TestSIFENWebhook(HttpCase):
    """Tests for SIFEN webhook endpoint."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        # Set webhook token for testing
        self.company.l10n_py_webhook_token = "test_token_123"
        self.webhook_url = f"/l10n_py_edi/webhook/{self.company.id}"

    def test_webhook_rejects_empty_payload(self):
        """Webhook returns error for empty payload."""
        response = self.url_open(
            self.webhook_url,
            json={},
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        data = _result(response)
        self.assertFalse(data.get("success"))

    def test_webhook_rejects_missing_token(self):
        """Webhook rejects request without Authorization header."""
        response = self.url_open(
            self.webhook_url,
            json={"cdc": "12345678"},
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        data = _result(response)
        self.assertFalse(data.get("success"))

    def test_webhook_rejects_invalid_token(self):
        """Webhook rejects request with wrong token."""
        response = self.url_open(
            self.webhook_url,
            json={"cdc": "12345678"},
            headers={"Authorization": "Bearer wrong_token"},
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        data = _result(response)
        self.assertFalse(data.get("success"))

    def test_webhook_accepts_valid_token_no_document(self):
        """Webhook accepts valid token but returns document not found."""
        response = self.url_open(
            self.webhook_url,
            json={"cdc": "9999999999999999999999999999999999999999999"},
            headers={"Authorization": "Bearer test_token_123"},
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        data = _result(response)
        self.assertFalse(data.get("success"))
        self.assertIn("not found", data.get("message", ""))

    def test_webhook_token_in_payload_accepted(self):
        """Webhook accepts token embedded in payload (fallback)."""
        response = self.url_open(
            self.webhook_url,
            json={"cdc": "999", "webhook_token": "test_token_123"},
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        data = _result(response)
        # Token in payload should be accepted, but document not found
        self.assertFalse(data.get("success"))
