from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..validators.ruc_validator import RUCValidator


@tagged("post_install", "-at_install", "l10n_py")
class TestRucValidator(TransactionCase):
    """Tests for Paraguayan RUC validator"""

    def test_check_digit_known_values(self):
        """Correct DV for known RUCs (verified against SET)"""
        self.assertEqual(
            RUCValidator._calculate_check_digit("80012345"),
            6,
            "RUC 80012345 should have DV=6",
        )
        self.assertEqual(
            RUCValidator._calculate_check_digit("4588955"),
            1,
            "RUC 4588955 should have DV=1",
        )
        self.assertEqual(
            RUCValidator._calculate_check_digit("80009401"),
            0,
            "RUC 80009401 should have DV=0",
        )
        self.assertEqual(
            RUCValidator._calculate_check_digit("80067890"),
            7,
            "RUC 80067890 should have DV=7",
        )
        self.assertEqual(
            RUCValidator._calculate_check_digit("80054321"),
            2,
            "RUC 80054321 should have DV=2",
        )

    def test_valid_ruc_with_correct_dv(self):
        """Valid RUCs with correct DV must pass validation"""
        valid_rucs = [
            "80012345-6",
            "4588955-1",
            "80009401-0",
        ]
        for ruc in valid_rucs:
            is_valid, error = RUCValidator.validate(ruc)
            self.assertTrue(
                is_valid,
                f"RUC {ruc} should be valid, error: {error}",
            )

    def test_invalid_ruc_wrong_dv(self):
        """RUC with wrong DV must be invalid"""
        is_valid, error = RUCValidator.validate("80012345-1")
        self.assertFalse(is_valid)
        self.assertIn("Invalid check digit", error)

    def test_invalid_ruc_too_short(self):
        """RUC too short must be invalid"""
        is_valid, error = RUCValidator.validate("12345")
        self.assertFalse(is_valid)

    def test_invalid_ruc_letters(self):
        """RUC with letters must be invalid"""
        self.assertFalse(RUCValidator.is_valid_format("1234567A"))

    def test_ruc_normalization(self):
        """Normalization adds correct DV"""
        normalized = RUCValidator.normalize("80012345-6")
        self.assertEqual(normalized, "80012345-6")

    def test_get_check_digit(self):
        """Get check digit"""
        dv = RUCValidator.get_check_digit("80012345")
        self.assertEqual(dv, "6")

    def test_format_ruc_includes_dv(self):
        """Format RUC with DV"""
        formatted = RUCValidator.format_ruc("80012345", include_dv=True)
        self.assertEqual(formatted, "80012345-6")

    def test_format_ruc_excludes_dv(self):
        """Format RUC without DV"""
        formatted = RUCValidator.format_ruc("80012345", include_dv=False)
        self.assertEqual(formatted, "80012345")
        self.assertNotIn("-", formatted)

    def test_get_ruc_number(self):
        """Extract only RUC number"""
        ruc_number = RUCValidator.get_ruc_number("80012345-6")
        self.assertEqual(ruc_number, "80012345")

    def test_get_ruc_number_from_full(self):
        """Extract RUC number from full format (concatenated digits)"""
        ruc_number = RUCValidator.get_ruc_number("800123456")
        self.assertEqual(ruc_number, "80012345")
