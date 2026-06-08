# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import api, fields, models
from odoo.exceptions import ValidationError

if TYPE_CHECKING:
    pass


class AccountAuthorization(models.Model):
    """Extension of account.authorization for multi-series support."""

    _inherit = "account.authorization"

    series_code = fields.Char(
        string="Series Code",
        size=3,
        help="3-digit series code (e.g., 001, 002)",
        index=True,
    )

    is_default = fields.Boolean(
        default=False,
        help="If True, this series is used by default for new invoices",
    )

    active_sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Active Sequence",
        help="Sequence used for this authorization series",
    )

    last_used_number = fields.Integer(
        string="Last Used Number",
        default=0,
        help="Last number used in this series",
    )

    @api.constrains("series_code", "company_id")
    def _check_series_unique(self) -> None:
        """Ensure series code is unique per company when authorization is valid."""
        for rec in self:
            if rec.series_code and rec.state == "valid":
                existing = self.search(
                    [
                        ("company_id", "=", rec.company_id.id),
                        ("series_code", "=", rec.series_code),
                        ("id", "!=", rec.id),
                        ("state", "=", "valid"),
                    ]
                )
                if existing:
                    raise ValidationError(
                        self.env._(
                            "Series %(series)s is already in use for company "
                            "%(company)s",
                            series=rec.series_code,
                            company=rec.company_id.name,
                        )
                    )

    @api.constrains("is_default", "company_id")
    def _check_default_per_company(self) -> None:
        """Ensure only one default per company when state is valid."""
        for rec in self:
            if rec.is_default and rec.state == "valid":
                existing = self.search(
                    [
                        ("company_id", "=", rec.company_id.id),
                        ("is_default", "=", True),
                        ("id", "!=", rec.id),
                        ("state", "=", "valid"),
                    ]
                )
                if existing:
                    raise ValidationError(
                        self.env._(
                            "Only one authorization can be default per company. "
                            "Company: %(company)s",
                            company=rec.company_id.name,
                        )
                    )

    def _get_next_sequence_number(self) -> str:
        """Get the next invoice number for this authorization series.

        Returns:
            Zero-padded 7-digit invoice number (e.g., '0000001').
        """
        self.ensure_one()

        if self.state != "valid":
            raise ValidationError(
                self.env._(
                    "Cannot generate number for inactive authorization %(name)s",
                    name=self.name,
                )
            )

        next_num = self.last_used_number + 1

        if self.invoice_number_from and next_num > self.invoice_number_to:
            raise ValidationError(
                self.env._(
                    "Authorization %(name)s is exhausted. Last number: %(to)s",
                    name=self.name,
                    to=self.invoice_number_to,
                )
            )

        self.last_used_number = next_num

        return str(next_num).zfill(7)

    def _invalidate_cdc(self) -> None:
        """Invalidate CDC when sequence is modified."""
        for rec in self:
            if not rec.series_code:
                continue
            # Find all invoices using this authorization that haven't been accepted
            if "l10n_py_edi_status" in self.env["account.move"]._fields:
                domain = [
                    ("l10n_py_authorization_id", "=", rec.id),
                    ("l10n_py_edi_status", "not in", ["accepted", "cancelled"]),
                ]
            else:
                domain = [("l10n_py_authorization_id", "=", rec.id)]

            moves = self.env["account.move"].search(domain)
            for move in moves:
                if move.l10n_py_cdc:
                    move.write({"l10n_py_cdc": False})

    @api.onchange("series_code")
    def _onchange_series_code(self) -> None:
        """Uppercase series code."""
        if self.series_code:
            self.series_code = self.series_code.upper().strip()
