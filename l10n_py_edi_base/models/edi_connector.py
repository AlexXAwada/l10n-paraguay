# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EDIConnector(models.Model):
    _name = "l10n_py.edi.connector"
    _description = "Connector EDI Paraguay"

    _company_provider_unique = models.Constraint(
        "UNIQUE (company_id, provider_type)",
        "Only one connector per (company, provider_type) is allowed.",
    )

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    provider_type = fields.Selection(
        selection=[],
        string="Proveedor",
        required=True,
    )
    environment = fields.Selection(
        [("test", "Tests"), ("prod", "Production")],
        default="test",
        required=True,
    )
    active = fields.Boolean(default=True)
    timeout = fields.Integer(default=30)

    # === Public interface (each provider must implement) ===

    def send_document(self, invoice_data):
        """Send document. Returns dict with success, result, error keys."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "Provider '%s' does not implement document sending",
                provider=self.provider_type,
            )
        )

    def check_status(self, document_id):
        """Check document status."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "El proveedor '%s' no implementa la consulta de estado",
                provider=self.provider_type,
            )
        )

    def cancel_document(self, document_id, reason=""):
        """Cancel an approved document."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "Provider '%s' does not implement cancellation",
                provider=self.provider_type,
            )
        )

    def preview_document(self, invoice_data):
        """Build XML without signing or sending. Returns XML string."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "Provider '%s' does not implement preview",
                provider=self.provider_type,
            )
        )

    def inutilize_range(self, data):
        """Inutilize a range of document numbers. Returns dict."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "Provider '%s' does not implement inutilization",
                provider=self.provider_type,
            )
        )

    def test_connection(self):
        """Test connectivity. Returns notification action."""
        self.ensure_one()
        raise UserError(
            self.env._(
                "Provider '%s' does not implement connection test",
                provider=self.provider_type,
            )
        )
