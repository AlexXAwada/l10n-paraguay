# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestAccountAuthorizationSequence(TransactionCase):
    """Tests for authorization series and sequence management."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()

        # Get demo company
        cls.company = cls.env.ref("base.main_company")

        # Get document type for Paraguay
        cls.doc_type = cls.env["l10n_latam.document.type"].search(
            [("country_id.code", "=", "PY")], limit=1
        )

        # Set up valid date range (state will be "valid" via _compute_state)
        cls.date_from = date.today()
        cls.date_to = cls.date_from + timedelta(days=365)

        # Create an authorization for testing (8-digit timbrado)
        cls.auth = cls.env["account.authorization"].create(
            {
                "name": "12345678",
                "company_id": cls.company.id,
                "establishment": "001",
                "expedition_point": "001",
                "invoice_number_from": 1,
                "invoice_number_to": 9999,
                "series": "AA",
                "series_code": "001",
                "is_default": True,
                "l10n_latam_document_type_id": cls.doc_type.id,
                "date_from": cls.date_from,
                "date_to": cls.date_to,
            }
        )

    def test_series_code_uniqueness_per_company(self) -> None:
        """Test that duplicate series codes raise error for valid authorizations."""
        with self.assertRaises(ValidationError):
            self.env["account.authorization"].create(
                {
                    "name": "23456789",
                    "company_id": self.company.id,
                    "establishment": "002",
                    "expedition_point": "001",
                    "invoice_number_from": 1,
                    "invoice_number_to": 9999,
                    "series": "AB",
                    "series_code": "001",  # Same as setUpClass auth
                    "is_default": False,
                    "l10n_latam_document_type_id": self.doc_type.id,
                    "date_from": self.date_from,
                    "date_to": self.date_to,
                }
            )

    def test_next_sequence_number_generation(self) -> None:
        """Test next sequence number generation."""
        # Initially last_used_number is 0
        self.assertEqual(self.auth.last_used_number, 0)

        # Get next number (state is "valid")
        next_num = self.auth._get_next_sequence_number()

        self.assertEqual(next_num, "0000001")
        self.assertEqual(self.auth.last_used_number, 1)

        # Get another
        next_num2 = self.auth._get_next_sequence_number()
        self.assertEqual(next_num2, "0000002")
        self.assertEqual(self.auth.last_used_number, 2)

    def test_exhaust_authorization_error(self) -> None:
        """Test that exhausted authorization raises error."""
        self.auth.write(
            {
                "invoice_number_from": 1,
                "invoice_number_to": 2,
                "last_used_number": 2,
            }
        )

        with self.assertRaises(ValidationError):
            self.auth._get_next_sequence_number()

    def test_cdc_invalidation_works(self) -> None:
        """Test that CDC invalidation method works without errors."""
        # Create an authorization with series
        auth_with_series = self.env["account.authorization"].create(
            {
                "name": "34567890",
                "company_id": self.company.id,
                "establishment": "002",
                "expedition_point": "002",
                "invoice_number_from": 1,
                "invoice_number_to": 9999,
                "series": "AC",
                "series_code": "002",
                "is_default": False,
                "l10n_latam_document_type_id": self.doc_type.id,
                "date_from": self.date_from,
                "date_to": self.date_to,
            }
        )

        # Should not raise any error
        auth_with_series._invalidate_cdc()
        self.assertTrue(True)  # If we get here, no error was raised

    def test_default_series_unique_per_company(self) -> None:
        """Test that only one default per company is allowed."""
        with self.assertRaises(ValidationError):
            self.env["account.authorization"].create(
                {
                    "name": "45678901",
                    "company_id": self.company.id,
                    "establishment": "003",
                    "expedition_point": "001",
                    "invoice_number_from": 1,
                    "invoice_number_to": 9999,
                    "series": "AD",
                    "series_code": "003",
                    "is_default": True,  # Should fail since first auth is default
                    "l10n_latam_document_type_id": self.doc_type.id,
                    "date_from": self.date_from,
                    "date_to": self.date_to,
                }
            )

    def test_onchange_uppercases_series_code(self) -> None:
        """Test that onchange uppercases the series code."""
        # Onchange uppercases the series code
        self.auth.series_code = "abc"
        self.auth._onchange_series_code()
        self.assertEqual(self.auth.series_code, "ABC")

    def test_expired_auth_cannot_generate_number(self) -> None:
        """Test that expired authorization cannot generate numbers."""
        # Create an authorization with past dates (state will be "expired")
        expired_auth = self.env["account.authorization"].create(
            {
                "name": "98765432",
                "company_id": self.company.id,
                "establishment": "005",
                "expedition_point": "001",
                "invoice_number_from": 1,
                "invoice_number_to": 9999,
                "series": "AF",
                "series_code": "005",
                "is_default": False,
                "l10n_latam_document_type_id": self.doc_type.id,
                "date_from": self.date_from - timedelta(days=100),
                "date_to": self.date_from - timedelta(days=1),
            }
        )
        # State should be "expired"
        self.assertEqual(expired_auth.state, "expired")

        with self.assertRaises(ValidationError):
            expired_auth._get_next_sequence_number()

    def test_different_series_codes_allowed(self) -> None:
        """Test that different series codes work without errors."""
        # Create authorization with different series code
        auth2 = self.env["account.authorization"].create(
            {
                "name": "56789012",
                "company_id": self.company.id,
                "establishment": "004",
                "expedition_point": "001",
                "invoice_number_from": 1,
                "invoice_number_to": 9999,
                "series": "AE",
                "series_code": "004",
                "is_default": False,
                "l10n_latam_document_type_id": self.doc_type.id,
                "date_from": self.date_from,
                "date_to": self.date_to,
            }
        )
        self.assertEqual(auth2.series_code, "004")
        self.assertFalse(auth2.is_default)

    def test_sequence_number_zfill(self) -> None:
        """Test that sequence numbers are zero-padded to 7 digits."""
        self.auth.last_used_number = 99
        next_num = self.auth._get_next_sequence_number()
        self.assertEqual(next_num, "0000100")
