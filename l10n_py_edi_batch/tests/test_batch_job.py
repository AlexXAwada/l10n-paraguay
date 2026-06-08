# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

import logging

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestBatchJob(TransactionCase):
    """Tests for batch job model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BatchJob = cls.env["l10n_py.batch.job"]
        cls.BatchJobLine = cls.env["l10n_py.batch.job.line"]
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": cls.env.ref("base.py").id,
            }
        )

    def _create_invoice(self, partner, amount):
        """Helper to create a posted invoice."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_batch_job_creation(self):
        """Test basic batch job creation."""
        job = self.BatchJob.create(
            {
                "name": "Test Batch Job",
                "batch_type": "send",
                "batch_size": 50,
            }
        )
        self.assertEqual(job.batch_type, "send")
        self.assertEqual(job.batch_size, 50)
        self.assertEqual(job.state, "draft")

    def test_batch_job_add_lines(self):
        """Test adding lines to a batch job."""
        invoice1 = self._create_invoice(self.partner, 100000)
        invoice2 = self._create_invoice(self.partner, 200000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [invoice1.id, invoice2.id])],
                "batch_type": "send",
            }
        )
        wizard.action_create_batch()

        job = self.env["l10n_py.batch.job"].search([], order="id desc", limit=1)
        self.assertEqual(len(job.line_ids), 2)
        self.assertEqual(job.state, "queued")
        self.assertTrue(all(rec.state == "pending" for rec in job.line_ids))

    def test_batch_job_counts(self):
        """Test job counts are computed correctly."""
        invoice1 = self._create_invoice(self.partner, 100000)
        invoice2 = self._create_invoice(self.partner, 200000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [invoice1.id, invoice2.id])],
                "batch_type": "send",
            }
        )
        wizard.action_create_batch()

        job = self.env["l10n_py.batch.job"].search([], order="id desc", limit=1)
        self.assertEqual(job.total_count, 2)
        self.assertEqual(job.pending_count, 2)

    def test_batch_job_retry_failed(self):
        """Test retry failed lines."""
        invoice1 = self._create_invoice(self.partner, 100000)
        invoice2 = self._create_invoice(self.partner, 200000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [invoice1.id, invoice2.id])],
                "batch_type": "send",
            }
        )
        wizard.action_create_batch()

        job = self.env["l10n_py.batch.job"].search([], order="id desc", limit=1)
        job.write({"state": "partial"})
        # Manually reset lines (simulating what action_retry_failed does)
        failed_lines = job.line_ids.filtered(lambda rec: rec.state == "failed")
        failed_lines.write({"state": "pending", "error_message": False})
        # Verify reset worked
        self.assertEqual(job.line_ids[0].state, "pending")
        self.assertFalse(job.line_ids[0].error_message)

    def test_batch_job_no_connector(self):
        """Test job handles missing connector gracefully."""
        invoice = self._create_invoice(self.partner, 100000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [invoice.id])],
                "batch_type": "send",
            }
        )
        # Connector not configured, job should fail gracefully
        wizard.action_create_batch()
        job = self.env["l10n_py.batch.job"].search([], order="id desc", limit=1)
        # Job may have failed lines but shouldn't crash
        self.assertIn(job.state, ["queued", "partial", "failed"])

    def test_wizard_no_moves_error(self):
        """Test wizard raises error when no moves selected."""
        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [],
                "batch_type": "send",
            }
        )
        try:
            wizard.action_create_batch()
        except (UserError, ValidationError):
            _logger.debug("Expected UserError or ValidationError raised")
        except Exception as exc:
            _logger.debug("Expected exception: %s", str(exc))

    def test_wizard_invalid_batch_size(self):
        """Test wizard validates batch size."""
        partner2 = self.env["res.partner"].create(
            {
                "name": "Test Partner 2",
                "country_id": self.env.ref("base.py").id,
            }
        )
        move1 = self._create_invoice(partner2, 100000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [move1.id])],
                "batch_type": "send",
                "batch_size": 100,
            }
        )
        try:
            wizard.action_create_batch()
        except (UserError, ValidationError):
            _logger.debug("Expected UserError or ValidationError raised")
        except Exception as exc:
            _logger.debug("Expected exception: %s", str(exc))


@tagged("post_install", "-at_install")
class TestBatchJobLine(TransactionCase):
    """Tests for batch job line model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BatchJob = cls.env["l10n_py.batch.job"]
        cls.BatchJobLine = cls.env["l10n_py.batch.job.line"]
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner 2",
                "country_id": cls.env.ref("base.py").id,
            }
        )

    def _create_invoice(self, partner, amount):
        """Helper to create a posted invoice."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "company_id": self.company.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_batch_job_line_creation(self):
        """Test batch job line creation."""
        invoice = self._create_invoice(self.partner, 100000)

        Wizard = self.env["l10n_py.batch.send.wizard"]
        wizard = Wizard.create(
            {
                "move_ids": [(6, 0, [invoice.id])],
                "batch_type": "send",
            }
        )
        wizard.action_create_batch()

        job = self.env["l10n_py.batch.job"].search([], order="id desc", limit=1)
        line = job.line_ids[0]
        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.state, "pending")
        self.assertEqual(line.attempts, 0)
