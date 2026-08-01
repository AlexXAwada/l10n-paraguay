# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestRejectResolution(TransactionCase):
    """Tests for EDI reject resolution functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "l10n_py_ruc": "123456789",
                "l10n_py_taxpayer_type": "1",
            }
        )

        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
                "l10n_py_ruc": "876543210",
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TEST",
                "type": "sale",
                "company_id": cls.company.id,
            }
        )

        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "journal_id": cls.journal.id,
                "company_id": cls.company.id,
                "l10n_py_edi_status": "rejected",
                "l10n_py_reject_code": "E001",
                "l10n_py_reject_message": "RUC not found in SET",
            }
        )

    def test_reject_fields_exist(self):
        """Test that reject tracking fields exist on account.move."""
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_code"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_message"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_action"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_date"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_fixed"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_reject_fix_field"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_retry_count"))
        self.assertTrue(hasattr(self.invoice, "l10n_py_last_retry"))

    def test_action_open_reject_wizard_returns_action(self):
        """Test that action_open_reject_wizard returns proper action."""
        action = self.invoice.action_open_reject_wizard()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "l10n_py.edi.reject.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["view_mode"], "form")

    def test_retry_only_for_rejected_documents(self):
        """Test that retry only works for rejected documents."""
        self.invoice.l10n_py_edi_status = "accepted"
        with self.assertRaises(UserError):
            self.invoice.action_retry_after_fix()

    def test_retry_clears_cdc_and_increments_count(self):
        """Test that retry clears CDC and increments counter."""
        old_cdc = "12345678901234567890123456789012345678901234"
        self.invoice.write({"l10n_py_cdc": old_cdc})

        with patch.object(
            self.invoice.__class__,
            "action_send_edi",
            return_value=True,
        ):
            result = self.invoice.action_retry_after_fix()

        self.assertTrue(result)
        self.assertFalse(self.invoice.l10n_py_cdc)
        self.assertEqual(self.invoice.l10n_py_retry_count, 1)
        self.assertTrue(self.invoice.l10n_py_reject_fixed)
        self.assertEqual(self.invoice.l10n_py_edi_status, "to_send")

    def test_retry_reverts_on_error(self):
        """Test that retry reverts CDC and status on error."""
        old_cdc = "12345678901234567890123456789012345678901234"
        self.invoice.write({"l10n_py_cdc": old_cdc})

        with patch.object(
            self.invoice.__class__,
            "action_send_edi",
            side_effect=Exception("API Error"),
        ):
            with self.assertRaises(UserError):
                self.invoice.action_retry_after_fix()

        self.assertEqual(self.invoice.l10n_py_cdc, old_cdc)
        self.assertEqual(self.invoice.l10n_py_edi_status, "rejected")

    def test_process_edi_error_stores_rejection_info(self):
        """Test that _process_edi_error stores rejection details."""
        result = {
            "estado": "rejected",
            "codigo_respuesta": "E002",
            "mensaje_respuesta": "Authorization expired",
        }

        with patch.object(
            self.invoice.__class__,
            "_get_edi_connector",
            return_value=False,
        ):
            self.invoice._process_edi_error(result)

        self.assertEqual(self.invoice.l10n_py_reject_code, "E002")
        self.assertEqual(self.invoice.l10n_py_reject_message, "Authorization expired")
        self.assertTrue(self.invoice.l10n_py_reject_date)


class TestResolveRejectWizard(TransactionCase):
    """Tests for the resolve reject wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "l10n_py_ruc": "123456789",
                "l10n_py_taxpayer_type": "1",
            }
        )

        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
                "l10n_py_ruc": "876543210",
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TEST",
                "type": "sale",
                "company_id": cls.company.id,
            }
        )

        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "journal_id": cls.journal.id,
                "company_id": cls.company.id,
                "l10n_py_edi_status": "rejected",
                "l10n_py_reject_code": "E001",
                "l10n_py_reject_message": "RUC not found",
            }
        )

        cls.wizard = cls.env["l10n_py.edi.reject.wizard"].create(
            {
                "move_id": cls.invoice.id,
            }
        )

    def test_wizard_fields_linked_to_move(self):
        """Test that wizard fields are properly linked to move."""
        self.assertEqual(self.wizard.reject_code, "E001")
        self.assertEqual(self.wizard.reject_message, "RUC not found")

    def test_fix_field_options_available(self):
        """Test that fix field options are available."""
        options = self.wizard._get_fix_field_options()
        self.assertTrue(len(options) > 0)
        field_names = [opt[0] for opt in options]
        self.assertIn("partner_ruc", field_names)
        self.assertIn("company_ruc", field_names)

    def test_wizard_partner_info_displayed(self):
        """Test that partner info is displayed in wizard."""
        self.assertEqual(self.wizard.partner_name, "Test Partner")
        self.assertEqual(self.wizard.partner_ruc, "123456789")


class TestBatchRetryWizard(TransactionCase):
    """Tests for the batch retry wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner1 = cls.env["res.partner"].create(
            {
                "name": "Partner 1",
                "l10n_py_ruc": "111111111",
                "l10n_py_taxpayer_type": "1",
            }
        )

        cls.partner2 = cls.env["res.partner"].create(
            {
                "name": "Partner 2",
                "l10n_py_ruc": "222222222",
                "l10n_py_taxpayer_type": "1",
            }
        )

        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
                "l10n_py_ruc": "876543210",
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TEST",
                "type": "sale",
                "company_id": cls.company.id,
            }
        )

        cls.invoice1 = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner1.id,
                "journal_id": cls.journal.id,
                "company_id": cls.company.id,
                "l10n_py_edi_status": "rejected",
            }
        )

        cls.invoice2 = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner2.id,
                "journal_id": cls.journal.id,
                "company_id": cls.company.id,
                "l10n_py_edi_status": "rejected",
            }
        )

        cls.wizard = cls.env["l10n_py.edi.batch.retry.wizard"].create(
            {
                "rejected_ids": [(6, 0, [cls.invoice1.id, cls.invoice2.id])],
                "fix_type": "all",
            }
        )

    def test_wizard_contains_selected_documents(self):
        """Test that wizard contains selected rejected documents."""
        self.assertEqual(len(self.wizard.rejected_ids), 2)

    def test_batch_retry_requires_documents(self):
        """Test that batch retry requires documents to be selected."""
        empty_wizard = self.env["l10n_py.edi.batch.retry.wizard"].create(
            {
                "fix_type": "all",
            }
        )
        with self.assertRaises(UserError):
            empty_wizard.action_apply_batch()

    def test_fix_type_options_available(self):
        """Test that fix type options are available."""
        self.assertTrue(len(self.wizard._fields["fix_type"].selection) > 0)
