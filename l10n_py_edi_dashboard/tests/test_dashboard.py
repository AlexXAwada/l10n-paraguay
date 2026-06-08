# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from odoo.tests import TransactionCase


class TestEDIDashboard(TransactionCase):
    """Test EDI Dashboard KPI computations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()
        cls.dashboard = cls.env["l10n_py.edi.dashboard"].create(
            {
                "company_id": cls.env.company.id,
            }
        )

    def test_dashboard_creation(self) -> None:
        """Test dashboard record can be created."""
        self.assertTrue(self.dashboard)
        self.assertEqual(self.dashboard.company_id, self.env.company)

    def test_action_open_pending_documents(self) -> None:
        """Test action returns correct window action."""
        action = self.dashboard.action_open_pending_documents()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move")
        # Check domain contains status filter
        domain = action.get("domain", [])
        domain_str = str(domain)
        self.assertIn("to_send", domain_str)

    def test_action_open_rejected_documents(self) -> None:
        """Test action returns correct window action."""
        action = self.dashboard.action_open_rejected_documents()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move")
        domain = action.get("domain", [])
        domain_str = str(domain)
        self.assertIn("rejected", domain_str)

    def test_action_open_contingency_documents(self) -> None:
        """Test action returns correct window action."""
        action = self.dashboard.action_open_contingency_documents()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move")

    def test_dashboard_fields_exist(self) -> None:
        """Test all KPI fields exist on the model."""
        field_names = [
            "total_documents",
            "pending_send",
            "sent_pending_response",
            "accepted_today",
            "rejected_today",
            "accepted_this_week",
            "accepted_this_month",
            "success_rate",
            "fe_count",
            "afe_count",
            "nce_count",
            "nde_count",
            "nre_count",
            "active_batches",
            "batch_success_rate",
            "contingency_pending",
            "company_id",
        ]
        for field_name in field_names:
            self.assertIn(
                field_name,
                self.dashboard._fields,
                f"Field {field_name} should exist on dashboard model",
            )
