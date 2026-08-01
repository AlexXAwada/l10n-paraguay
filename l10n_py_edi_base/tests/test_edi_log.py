# l10n_py_edi_base/tests/test_edi_log.py

import logging
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_py")
class TestEDILog(TransactionCase):
    """Tests para l10n_py.edi.log"""

    def test_log_operation_success(self):
        """Create successful operation log"""
        log = self.env["l10n_py.edi.log"].log_operation(
            operation_type="send",
            provider="sifen",
            execution_time=150.5,
            success=True,
        )
        self.assertTrue(log)
        self.assertTrue(log.success)
        self.assertFalse(log.error)

    def test_log_operation_error(self):
        """Create error operation log"""
        # Suppress ERROR log to prevent CI failures
        with patch.object(
            logging.getLogger("odoo.addons.l10n_py_edi_base.models.l10n_py_edi_log"),
            "error",
        ):
            log = self.env["l10n_py.edi.log"].log_operation(
                operation_type="send",
                provider="sifen",
                execution_time=500.0,
                success=False,
                error_message="Connection timeout",
            )
        self.assertTrue(log)
        self.assertFalse(log.success)
        self.assertTrue(log.error)
        self.assertEqual(log.error_message, "Connection timeout")

    def test_error_computed(self):
        """Error field computed correctly"""
        log = self.env["l10n_py.edi.log"].create(
            {
                "operation_type": "send",
                "provider": "sifen",
                "status_code": 500,
                "success": False,
            }
        )
        self.assertTrue(log.error)

        log2 = self.env["l10n_py.edi.log"].create(
            {
                "operation_type": "send",
                "provider": "sifen",
                "status_code": 200,
                "success": True,
            }
        )
        self.assertFalse(log2.error)

    def test_duration_human_ms(self):
        """Formateo < 1000ms"""
        log = self.env["l10n_py.edi.log"].create(
            {
                "operation_type": "send",
                "provider": "sifen",
                "execution_time": 150.5,
            }
        )
        self.assertIn("ms", log.duration_human)

    def test_duration_human_seconds(self):
        """Formateo >= 1000ms"""
        log = self.env["l10n_py.edi.log"].create(
            {
                "operation_type": "send",
                "provider": "sifen",
                "execution_time": 2500.0,
            }
        )
        self.assertIn("s", log.duration_human)
