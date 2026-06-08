from __future__ import annotations

from odoo import fields
from odoo.tests import TransactionCase


class TestEDISummary(TransactionCase):
    """Tests for EDI summary module."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()

        cls.company = cls.env.ref("base.main_company")

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "test@example.com",
                "country_id": cls.env.ref("base.py").id,
            }
        )

    def test_summary_creation(self) -> None:
        """Test that we can create a summary record."""
        summary = self.env["l10n_py.edi.summary"].create(
            {
                "date": fields.Date.context_today(self),
                "company_id": self.company.id,
                "total_documents": 10,
                "accepted_today": 8,
                "rejected_today": 1,
                "pending_response": 1,
                "success_rate": 88.0,
            }
        )
        self.assertTrue(summary.id, "Summary should be created")
        self.assertEqual(summary.total_documents, 10)

    def test_compute_daily_summary(self) -> None:
        """Test daily summary computation."""
        summary_model = self.env["l10n_py.edi.summary"]
        result = summary_model._compute_daily_summary()
        self.assertIn("date", result)
        self.assertIn("company_id", result)
        self.assertIn("total_documents", result)
        self.assertIn("accepted_today", result)
        self.assertIn("rejected_today", result)

    def test_cron_generate_daily_summary(self) -> None:
        """Test that cron generates summary."""
        summary_model = self.env["l10n_py.edi.summary"]
        summary_model._cron_generate_daily_summary()
        # Check if summary was created for today
        today = fields.Date.context_today(self)
        summary = summary_model.search(
            [
                ("date", "=", today),
                ("company_id", "=", self.company.id),
            ]
        )
        self.assertTrue(summary, "Summary should be created by cron")

    def test_action_view_documents(self) -> None:
        """Test action to view documents."""
        summary = self.env["l10n_py.edi.summary"].create(
            {
                "date": fields.Date.context_today(self),
                "company_id": self.company.id,
                "total_documents": 5,
            }
        )
        action = summary.action_view_documents()
        self.assertEqual(action["res_model"], "account.move")
        # Check that domain contains invoice_date condition
        domain = action.get("domain", [])
        has_date_filter = any(item[0] == "invoice_date" for item in domain)
        self.assertTrue(has_date_filter, "Domain should contain invoice_date filter")

    def test_email_sent_flag(self) -> None:
        """Test email sent flag."""
        summary = self.env["l10n_py.edi.summary"].create(
            {
                "date": fields.Date.context_today(self),
                "company_id": self.company.id,
                "email_sent": False,
            }
        )
        self.assertFalse(summary.email_sent)
        summary.write({"email_sent": True, "email_sent_date": fields.Datetime.now()})
        self.assertTrue(summary.email_sent)
        self.assertTrue(summary.email_sent_date)

    def test_document_type_counts(self) -> None:
        """Test document type counts are present."""
        summary = self.env["l10n_py.edi.summary"].create(
            {
                "date": fields.Date.context_today(self),
                "company_id": self.company.id,
                "fe_count": 5,
                "afe_count": 2,
                "nce_count": 1,
                "nde_count": 1,
                "nre_count": 1,
            }
        )
        self.assertEqual(summary.fe_count, 5)
        self.assertEqual(summary.afe_count, 2)
        self.assertEqual(summary.nce_count, 1)
        self.assertEqual(summary.nde_count, 1)
        self.assertEqual(summary.nre_count, 1)
