# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSIFENConnector(TransactionCase):
    """Test SIFEN connector model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"l10n_py_ruc": "80012345"})

    def test_create_sifen_connector(self):
        """Test creating a SIFEN connector."""
        self.env["l10n_py.edi.connector"].sudo().search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        connector = self.env["l10n_py.edi.connector"].create(
            {
                "name": "SIFEN Test",
                "company_id": self.company.id,
                "provider_type": "sifen",
                "environment": "test",
            }
        )
        self.assertEqual(connector.provider_type, "sifen")
        self.assertEqual(connector.environment, "test")

    def test_company_provider_unique_constraint(self):
        """Test that one connector per (company, provider_type) is allowed.

        The constraint is unique(company_id, provider_type), so multiple
        connectors for the same company are allowed if provider_type differs.
        Duplicate (company, provider_type) raises IntegrityError.
        """
        # Clean up any existing connectors first (demo data + previous tests)
        self.env["l10n_py.edi.connector"].sudo().search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        # Create first connector
        self.env["l10n_py.edi.connector"].create(
            {
                "name": "Connector1",
                "company_id": self.company.id,
                "provider_type": "sifen",
                "environment": "test",
            }
        )
        # Duplicate must raise IntegrityError
        with self.assertRaises(IntegrityError):
            self.env["l10n_py.edi.connector"].create(
                {
                    "name": "Connector 2",
                    "company_id": self.company.id,
                    "provider_type": "sifen",
                    "environment": "test",
                }
            )

    @patch(
        "odoo.addons.l10n_py_edi_sifen.models.edi_connector"
        ".EDIConnector._sifen_get_consulta"
    )
    def test_test_connection(self, mock_consulta):
        """Test test_connection returns notification action."""
        mock_instance = mock_consulta.return_value
        mock_instance.consultar_ruc.return_value = True
        mock_instance.cleanup.return_value = None

        self.env["l10n_py.edi.connector"].sudo().search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        connector = self.env["l10n_py.edi.connector"].create(
            {
                "name": "SIFEN Test",
                "company_id": self.company.id,
                "provider_type": "sifen",
                "environment": "test",
            }
        )
        result = connector.test_connection()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
