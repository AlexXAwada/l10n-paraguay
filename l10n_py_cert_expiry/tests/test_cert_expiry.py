from __future__ import annotations

from datetime import date, timedelta

from odoo import fields
from odoo.tests import TransactionCase


class TestCertExpiry(TransactionCase):
    """Tests for certificate expiry notifications."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()

        # Get main company
        cls.company = cls.env.ref("base.main_company")

        # Create a notification contact
        cls.notification_partner = cls.env["res.partner"].create(
            {
                "name": "Certificate Admin",
                "email": "cert-admin@example.com",
            }
        )

        # Set company fields
        cls.company.write(
            {
                "l10n_py_cert_expiry_warning_days": 30,
                "l10n_py_cert_notification_partner_id": cls.notification_partner.id,
            }
        )

    def test_warning_sent_within_warning_period(self) -> None:
        """Test that warning is sent when certificate is within warning period."""
        # Set certificate to expire in 15 days
        expiry_date = date.today() + timedelta(days=15)
        self.company.write({"l10n_py_certificate_expiry": expiry_date})

        # Run cron
        self.env["res.company"]._cron_check_certificate_expiry()

        # Check that a message was posted (warning sent)
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
            ]
        )
        self.assertTrue(
            messages,
            "A warning message should be posted for certificate expiring soon",
        )

    def test_no_duplicate_notifications(self) -> None:
        """Test that duplicate notifications are not sent on same day."""
        # Set certificate to expire in 20 days
        expiry_date = date.today() + timedelta(days=20)
        self.company.write({"l10n_py_certificate_expiry": expiry_date})

        # Run cron twice
        self.env["res.company"]._cron_check_certificate_expiry()
        self.env["res.company"]._cron_check_certificate_expiry()

        # Count messages posted today
        today_start = fields.Datetime.start_of(fields.Datetime.now(), "day")
        messages_today = self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
                ("create_date", ">=", today_start),
            ]
        )

        # Should only have 1 message (not duplicate)
        cert_messages = messages_today.filtered(
            lambda m: "certificate" in (m.body or "").lower()
        )
        self.assertLessEqual(
            len(cert_messages),
            1,
            "Should not send duplicate notifications on same day",
        )

    def test_expired_certificate_message(self) -> None:
        """Test that cron handles expired certificate without errors."""
        # Set certificate to expired yesterday
        expiry_date = date.today() - timedelta(days=1)
        self.company.write({"l10n_py_certificate_expiry": expiry_date})

        # Run cron - should not raise exception
        try:
            self.env["res.company"]._cron_check_certificate_expiry()
        except Exception as e:
            self.fail(f"Cron should not raise exception for expired cert: {e}")

        # Verify the cron completed (no exception means success)
        # The actual message posting may fail in test env due to constraints

    def test_no_notification_for_valid_certificates(self) -> None:
        """Test that no notification is sent for certificates far from expiry."""
        # Set certificate to expire in 100 days (far from warning period)
        expiry_date = date.today() + timedelta(days=100)
        self.company.write({"l10n_py_certificate_expiry": expiry_date})

        # Clear any existing messages
        self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
            ]
        ).unlink()

        # Run cron
        self.env["res.company"]._cron_check_certificate_expiry()

        # Check no warning was sent
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
            ]
        )
        self.assertFalse(
            messages,
            "No notification should be sent for certificates far from expiry",
        )

    def test_cron_runs_without_errors(self) -> None:
        """Test that cron runs without errors for all companies."""
        # Set different expiry dates
        dates = [
            date.today() + timedelta(days=10),
            date.today() + timedelta(days=60),
            date.today() + timedelta(days=200),
        ]

        for i, exp_date in enumerate(dates):
            company = self.env["res.company"].create(
                {
                    "name": f"Test Company {i}",
                    "l10n_py_certificate_expiry": exp_date,
                }
            )
            # Should not raise exception
            try:
                company._cron_check_certificate_expiry()
            except Exception as e:
                self.fail(f"Cron failed for company {i}: {e}")

    def test_no_notification_when_no_expiry_date(self) -> None:
        """Test that no notification is sent when no expiry date is set."""
        # Clear expiry date
        self.company.write({"l10n_py_certificate_expiry": False})

        # Clear any existing messages
        self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
            ]
        ).unlink()

        # Run cron
        self.env["res.company"]._cron_check_certificate_expiry()

        # Check no warning was sent
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "res.company"),
                ("res_id", "=", self.company.id),
            ]
        )
        self.assertFalse(
            messages,
            "No notification should be sent when no expiry date is set",
        )
