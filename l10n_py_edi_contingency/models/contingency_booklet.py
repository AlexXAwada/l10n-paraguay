# l10n_py_edi_contingency/models/contingency_booklet.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odoo import api, fields, models
from odoo.exceptions import UserError

if TYPE_CHECKING:
    from odoo.addons.base.models.res_company import Company


class ContingencyBooklet(models.Model):
    """Physical booklet from SET for offline contingency operation.

    Each booklet contains a range of pre-printed numbers that can be
    used when SIFEN is unreachable. Numbers are assigned sequentially
    and tracked to avoid duplicates.
    """

    _name = "l10n_py.contingency.booklet"
    _description = "Contingency Booklet (SET physical booklet)"
    _order = "activation_date desc, name"
    _check_company_auto = True

    name: str = fields.Char(
        string="Booklet Number",
        required=True,
        help="Physical booklet number from SET (e.g., CONT-2024-001)",
    )
    company_id: Company = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    start_number: int = fields.Integer(
        string="Start Number",
        required=True,
        help="First document number in this booklet",
    )
    end_number: int = fields.Integer(
        string="End Number",
        required=True,
        help="Last document number in this booklet",
    )
    used_count: int = fields.Integer(
        string="Used",
        compute="_compute_used",
        store=True,
    )
    remaining: int = fields.Integer(
        string="Remaining",
        compute="_compute_remaining",
        store=True,
    )
    state: str = fields.Selection(
        [
            ("active", "Active"),
            ("exhausted", "Exhausted"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="active",
        required=True,
    )
    activation_date: fields.Date = fields.Date(
        string="Activation Date",
        help="Date when this booklet started being used",
    )
    notes: str = fields.Text(string="Notes")

    _sql_constraints = [
        (
            "unique_name_company",
            "unique(name, company_id)",
            "A booklet with this number already exists for this company.",
        ),
        (
            "start_end_check",
            "CHECK(start_number > 0 AND end_number >= start_number)",
            "End number must be greater than or equal to start number.",
        ),
    ]

    @api.depends("name", "company_id")
    def _compute_used(self) -> None:
        """Count how many contingency invoices use this booklet."""
        for rec in self:
            count = self.env["account.move"].search_count(
                [
                    ("l10n_py_contingency_booklet_id", "=", rec.id),
                    ("l10n_py_edi_status", "!=", "draft"),
                ]
            )
            rec.used_count = count

    @api.depends("start_number", "end_number", "used_count")
    def _compute_remaining(self) -> None:
        """Calculate remaining numbers in the booklet."""
        for rec in self:
            total = rec.end_number - rec.start_number + 1
            rec.remaining = max(0, total - rec.used_count)

    def _get_next_number(self) -> int:
        """Get the next available document number from this booklet.

        Returns:
            Next document number to use.

        Raises:
            UserError: If no numbers remain in the booklet.
        """
        self.ensure_one()
        if self.remaining <= 0:
            raise UserError(
                self.env._(
                    "Booklet %(booklet)s has no remaining numbers. "
                    "Please activate a new booklet.",
                    booklet=self.name,
                )
            )

        # Find the highest used number and return next
        used_numbers = self.env["account.move"].search(
            [
                ("l10n_py_contingency_booklet_id", "=", self.id),
                ("l10n_py_contingency_number", "!=", False),
            ],
            order="l10n_py_contingency_number desc",
            limit=1,
        )

        if used_numbers and used_numbers.l10n_py_contingency_number:
            next_num = int(used_numbers.l10n_py_contingency_number) + 1
        else:
            next_num = self.start_number

        if next_num > self.end_number:
            raise UserError(
                self.env._(
                    "Booklet %(booklet)s range exhausted. "
                    "Next number (%(next)s) exceeds end number (%(end)s).",
                    booklet=self.name,
                    next=next_num,
                    end=self.end_number,
                )
            )

        return next_num

    def action_activate(self) -> bool:
        """Mark this booklet as active.

        Returns:
            True on success.
        """
        for rec in self:
            if rec.state == "exhausted":
                raise UserError(self.env._("Cannot activate an exhausted booklet."))
            rec.write({"state": "active"})
        return True

    def action_deactivate(self) -> bool:
        """Mark this booklet as cancelled.

        Returns:
            True on success.

        Raises:
            UserError: If booklet has used numbers.
        """
        for rec in self:
            if rec.state == "active" and rec.used_count > 0:
                raise UserError(
                    self.env._(
                        "Cannot cancel an active booklet with used numbers. "
                        "Please exhaust it first or deactivate all invoices."
                    )
                )
            rec.write({"state": "cancelled"})
        return True

    @api.onchange("start_number", "end_number")
    def _onchange_range(self) -> dict[str, Any] | None:
        """Auto-set activation date when booklet is activated."""
        if (
            self.start_number
            and self.end_number
            and self.start_number > self.end_number
        ):
            return {
                "warning": {
                    "title": self.env._("Invalid Range"),
                    "message": self.env._(
                        "End number must be greater than or equal to start number."
                    ),
                }
            }
        return None
