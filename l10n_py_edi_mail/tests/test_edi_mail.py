from __future__ import annotations

from odoo.tests import TransactionCase


class TestEDIMail(TransactionCase):
    """Tests for EDI email notifications module."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()

        # Get demo company
        cls.company = cls.env.ref("base.main_company")

        # Create a partner with email
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
                "country_id": cls.env.ref("base.py").id,
            }
        )

        # Create account move (invoice) without lines
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "company_id": cls.company.id,
            }
        )

    def test_email_recipients_computed(self) -> None:
        """Test that email recipients are computed correctly."""
        self.assertTrue(
            self.invoice.l10n_py_email_recipient_ids,
            "Partner with email should be a recipient",
        )
        self.assertIn(
            self.partner,
            self.invoice.l10n_py_email_recipient_ids,
            "Partner should be in recipients",
        )

    def test_auto_send_email_default(self) -> None:
        """Test that auto send email is True by default."""
        self.assertTrue(
            self.invoice.l10n_py_auto_send_email,
            "Auto send email should be True by default",
        )

    def test_notification_sent_initially_false(self) -> None:
        """Test that notification sent is initially False."""
        self.assertFalse(
            self.invoice.l10n_py_email_notification_sent,
            "Notification sent should be False initially",
        )

    def test_recipients_empty_without_partner_email(self) -> None:
        """Test that recipients are empty when partner has no email."""
        partner_no_email = self.env["res.partner"].create(
            {
                "name": "Partner Without Email",
                "country_id": self.env.ref("base.py").id,
            }
        )

        invoice_no_email = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner_no_email.id,
                "company_id": self.company.id,
            }
        )

        self.assertFalse(
            invoice_no_email.l10n_py_email_recipient_ids,
            "Recipients should be empty when partner has no email",
        )

    def test_email_notification_date_initially_false(self) -> None:
        """Test that notification date is initially False."""
        self.assertFalse(
            self.invoice.l10n_py_email_notification_date,
            "Notification date should be False initially",
        )

    def test_auto_send_disabled_prevents_email(self) -> None:
        """Test that disabling auto send prevents email."""
        self.invoice.write({"l10n_py_auto_send_email": False})
        result = self.invoice._send_edi_notification_email()
        self.assertFalse(result, "Should return False when auto send is disabled")

    def test_no_recipients_returns_false(self) -> None:
        """Test that no recipients returns False."""
        partner_no_email = self.env["res.partner"].create(
            {
                "name": "No Email Partner",
                "country_id": self.env.ref("base.py").id,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner_no_email.id,
                "company_id": self.company.id,
                "l10n_py_edi_status": "accepted",
            }
        )
        result = invoice._send_edi_notification_email()
        self.assertFalse(result, "Should return False when no recipients")

    def test_cron_finds_pending_notifications(self) -> None:
        """Test that cron finds pending notifications correctly."""
        # Create a document in accepted status without notification sent
        pending_doc = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "l10n_py_edi_status": "accepted",
                "l10n_py_email_notification_sent": False,
                "l10n_py_auto_send_email": True,
            }
        )

        # Search for pending notifications
        pending = self.env["account.move"].search(
            [
                ("l10n_py_edi_status", "in", ["accepted", "rejected", "cancelled"]),
                ("l10n_py_auto_send_email", "=", True),
                ("l10n_py_email_notification_sent", "=", False),
            ]
        )

        self.assertIn(
            pending_doc,
            pending,
            "Pending document should be found by cron search",
        )

    def test_mark_notification_sent_works(self) -> None:
        """Test that marking notification as sent works."""
        self.invoice.write(
            {
                "l10n_py_email_notification_sent": True,
                "l10n_py_email_notification_date": self.env.cr.now(),
            }
        )
        self.assertTrue(self.invoice.l10n_py_email_notification_sent)
        self.assertTrue(self.invoice.l10n_py_email_notification_date)
