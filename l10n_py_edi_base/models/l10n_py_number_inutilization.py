# l10n_py_edi_base/models/l10n_py_number_inutilization.py

import logging
import time

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MAX_INUTILIZATION_RANGE = 1000


class NumberInutilization(models.Model):
    """Inutilization of electronic document numbers.

    Allows inutilizing ranges of numbers that will not be used,
    notifying SIFEN to keep the sequence consistent.
    """

    _name = "l10n_py.number.inutilization"
    _description = "Number Inutilization"
    _order = "create_date desc"

    authorization_id = fields.Many2one(
        "account.authorization",
        string="Authorization Number",
        required=True,
        ondelete="restrict",
    )

    number_from = fields.Integer(
        string="Number From",
        required=True,
    )

    number_to = fields.Integer(
        string="Number To",
        required=True,
    )

    motive = fields.Text(
        string="Reason",
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        string="State",
        default="draft",
        readonly=True,
    )

    company_id = fields.Many2one(
        related="authorization_id.company_id",
        store=True,
    )

    quantity = fields.Integer(
        string="Quantity",
        compute="_compute_quantity",
    )

    def _compute_quantity(self):
        for rec in self:
            rec.quantity = rec.number_to - rec.number_from + 1

    # ============== CONSTRAINTS ==============

    @api.constrains("number_from", "number_to")
    def _check_range(self):
        for rec in self:
            if rec.number_from <= 0 or rec.number_to <= 0:
                raise ValidationError(self.env._("Numbers must be greater than zero."))
            if rec.number_to < rec.number_from:
                raise ValidationError(
                    self.env._(
                        "The ending number must be greater than or "
                        "equal to the starting number."
                    )
                )
            quantity = rec.number_to - rec.number_from + 1
            if quantity > MAX_INUTILIZATION_RANGE:
                raise ValidationError(
                    self.env._(
                        "The maximum inutilization range is "
                        "%(max)s numbers (requested: %(qty)s).",
                        max=MAX_INUTILIZATION_RANGE,
                        qty=quantity,
                    )
                )

    @api.constrains("number_from", "number_to", "authorization_id")
    def _check_within_authorization_range(self):
        """Verify that the range is within the authorization range."""
        for rec in self:
            auth = rec.authorization_id
            if rec.number_from < auth.invoice_number_from:
                raise ValidationError(
                    self.env._(
                        "The starting number is outside the range "
                        "of the authorization (minimum: %(min)s).",
                        min=auth.invoice_number_from,
                    )
                )
            if rec.number_to > auth.invoice_number_to:
                raise ValidationError(
                    self.env._(
                        "The ending number is outside the range "
                        "of the authorization (maximum: %(max)s).",
                        max=auth.invoice_number_to,
                    )
                )

    @api.constrains("number_from", "number_to", "authorization_id")
    def _check_no_used_numbers(self):
        """Verify that no number in the range has already been used."""
        for rec in self:
            used = self.env["account.move"].search_count(
                [
                    ("l10n_py_authorization_id", "=", rec.authorization_id.id),
                    ("l10n_py_invoice_number", ">=", rec.number_from),
                    ("l10n_py_invoice_number", "<=", rec.number_to),
                    ("state", "=", "posted"),
                ]
            )
            if used:
                raise ValidationError(
                    self.env._(
                        "There are %(count)s number(s) in the range that "
                        "have already been used in confirmed invoices.",
                        count=used,
                    )
                )

    # ============== ACTIONS ==============

    def action_send(self):
        """Send inutilization to SIFEN via EDI connector."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(
                self.env._("Only inutilizations in draft state can be sent.")
            )

        connector = (
            self.env["l10n_py.edi.connector"]
            .sudo()
            .search([("company_id", "=", self.company_id.id)], limit=1)
        )
        if not connector:
            raise UserError(self.env._("No EDI connector configured for this company."))

        auth = self.authorization_id
        data = {
            "timbrado": auth.name or "",
            "establecimiento": auth.establishment or "001",
            "punto": auth.expedition_point or "001",
            "numeroDesde": str(self.number_from).zfill(7),
            "numeroHasta": str(self.number_to).zfill(7),
            "tipoDocumento": 1,  # default to FE (electronic invoice)
            "motivo": self.motive or "",
        }

        try:
            t0 = time.time()
            response = connector.inutilize_range(data)
            duration_ms = (time.time() - t0) * 1000

            # Log operation
            try:
                self.env["l10n_py.edi.log"].log_operation(
                    operation_type="inutilize",
                    provider="sifen",
                    response_data=response,
                    success=response.get("success", False),
                    error_message=response.get("error"),
                    execution_time=duration_ms,
                )
            except Exception as log_err:
                _logger.warning("Failed to log inutilization: %s", str(log_err))

            if response.get("success"):
                self.state = "accepted"
            else:
                self.state = "rejected"
                _logger.warning("Inutilization rejected: %s", response.get("error"))
                raise UserError(
                    self.env._(
                        "Inutilization error: %(error)s", error=response.get("error")
                    )
                )
        except UserError:
            raise
        except Exception as e:
            self.state = "rejected"
            raise UserError(
                self.env._(
                    "Error sending inutilization request: %(error)s", error=str(e)
                )
            ) from e
