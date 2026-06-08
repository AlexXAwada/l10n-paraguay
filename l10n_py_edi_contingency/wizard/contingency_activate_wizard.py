# l10n_py_edi_contingency/wizard/contingency_activate_wizard.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from odoo import api, fields, models
from odoo.exceptions import UserError

if TYPE_CHECKING:
    pass


class ContingencyActivateWizard(models.TransientModel):
    """Wizard to activate contingency mode for one or more invoices.

    This wizard assigns a contingency booklet to selected invoices,
    enabling offline operation when SIFEN is unreachable.
    """

    _name = "l10n_py.contingency.activate.wizard"
    _description = "Activate contingency mode for invoices"

    booklet_id: models.Model = fields.Many2one(
        "l10n_py.contingency.booklet",
        string="Booklet",
        required=True,
        domain="[('state', '=', 'active'), ('remaining', '>', 0)]",
        help="Select an active booklet with available numbers",
    )

    @api.model
    def default_get(self, fields_list: list[str]) -> dict[str, Any]:
        """Pre-select a booklet based on context.

        Args:
            fields_list: Fields being retrieved.

        Returns:
            Default values dictionary.
        """
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return res

        # Try to find a suitable booklet for the company
        moves = self.env["account.move"].browse(active_ids)
        company = moves[0].company_id if moves else self.env.company

        # Find active booklet with remaining numbers
        booklet = self.env["l10n_py.contingency.booklet"].search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "active"),
            ],
            limit=1,
        )
        if booklet:
            res["booklet_id"] = booklet.id

        return res

    def action_activate(self) -> dict[str, Any]:
        """Mark selected invoices as contingency mode.

        Assigns contingency numbers from the selected booklet to each
        invoice. The first available number is assigned to each document.

        Returns:
            Notification action.
        """
        self.ensure_one()
        if not self.booklet_id:
            raise UserError(self.env._("Please select a booklet"))

        if self.booklet_id.remaining <= 0:
            raise UserError(
                self.env._(
                    "Booklet %(booklet)s has no remaining numbers. "
                    "Please select a different booklet.",
                    booklet=self.booklet_id.name,
                )
            )

        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            raise UserError(self.env._("No invoices selected"))

        moves = self.env["account.move"].browse(active_ids)

        # Filter moves that can use contingency
        valid_moves = moves.filtered(
            lambda m: m.l10n_py_edi_status in ("draft", "pending") and not m.l10n_py_cdc
        )

        if not valid_moves:
            raise UserError(
                self.env._(
                    "No valid invoices found. Invoices must be in draft or "
                    "pending status with no CDC assigned."
                )
            )

        activated = 0
        for move in valid_moves:
            # Check if booklet has numbers left
            if self.booklet_id.remaining <= 0:
                raise UserError(
                    self.env._(
                        "Booklet %(booklet)s exhausted after activating "
                        "%(count)s invoices.",
                        booklet=self.booklet_id.name,
                        count=activated,
                    )
                )

            # Assign contingency number from booklet
            # (number is assigned inside _prepare_contingency_document)

            # Update invoice with contingency data
            move.write(
                {
                    "l10n_py_contingency_booklet_id": self.booklet_id.id,
                    "l10n_py_emission_type": "2",  # Contingency
                    "l10n_py_edi_status": "to_send",
                }
            )

            # Generate contingency XML (no CDC, no SIFEN)
            move._prepare_contingency_document()

            activated += 1

        # Log the activation
        self.env["l10n_py.edi.log"].log_operation(
            operation_type="contingency_activate",
            provider="local",
            request_data={
                "booklet_id": self.booklet_id.id,
                "booklet_name": self.booklet_id.name,
                "activated_count": activated,
            },
            success=True,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Contingency Mode Activated"),
                "message": self.env._(
                    "%(count)s invoice(s) activated with contingency booklet "
                    "%(booklet)s.",
                    count=activated,
                    booklet=self.booklet_id.name,
                ),
                "type": "success",
                "sticky": False,
            },
        }
