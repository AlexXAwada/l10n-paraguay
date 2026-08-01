# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import api, fields, models

if TYPE_CHECKING:
    pass


class ResolveRejectWizard(models.TransientModel):
    """Wizard to resolve a rejected EDI document."""

    _name = "l10n_py.edi.reject.wizard"
    _description = "Resolve EDI Rejection"

    move_id = fields.Many2one(
        comodel_name="account.move",
        required=True,
        readonly=True,
    )

    reject_code = fields.Char(
        readonly=True,
        related="move_id.l10n_py_reject_code",
    )

    reject_message = fields.Text(
        readonly=True,
        related="move_id.l10n_py_reject_message",
    )

    suggested_action = fields.Char(
        readonly=True,
        related="move_id.l10n_py_reject_action",
    )

    fix_field = fields.Selection(
        selection="_get_fix_field_options",
        default="other",
        help="Select the field that needs to be corrected",
    )

    partner_name = fields.Char(
        related="move_id.partner_id.name",
        readonly=True,
    )

    partner_ruc = fields.Char(
        related="move_id.partner_id.l10n_py_ruc",
        readonly=True,
    )

    partner_doc_number = fields.Char(
        related="move_id.partner_id.l10n_py_doc_number",
        readonly=True,
    )

    partner_taxpayer_type = fields.Selection(
        related="move_id.partner_id.l10n_py_taxpayer_type",
        readonly=True,
    )

    new_partner_ruc = fields.Char(
        help="Enter corrected RUC for the partner",
    )

    new_partner_doc_number = fields.Char(
        help="Enter corrected document number for the partner",
    )

    new_partner_taxpayer_type = fields.Selection(
        selection=[
            ("1", "Taxpayer (has RUC)"),
            ("2", "Non-Taxpayer (no RUC)"),
        ],
        help="Select corrected taxpayer type",
    )

    company_ruc = fields.Char(
        related="move_id.company_id.l10n_py_ruc",
        readonly=True,
    )

    new_company_ruc = fields.Char(
        help="Enter corrected company RUC",
    )

    notes = fields.Text(
        help="Notes about why this fix is being applied",
    )

    @api.model
    def _get_fix_field_options(self) -> list[tuple[str, str]]:
        """Get available fields to fix based on error code.

        Returns:
            List of (value, label) tuples.
        """
        options = [
            ("partner_ruc", "Partner RUC (wrong or invalid)"),
            ("partner_doc_number", "Partner Document Number (wrong)"),
            ("partner_taxpayer_type", "Partner Taxpayer Type (wrong type)"),
            ("company_ruc", "Company RUC (wrong or invalid)"),
            ("amount_total", "Total Amount (amount mismatch)"),
            ("tax_amount", "Tax Amount (IVA calculation error)"),
            ("partner_address", "Partner Address (incomplete address)"),
            ("other", "Other (manual review required)"),
        ]
        return options

    def action_apply_fix(self) -> dict:
        """Apply the selected fix and retry the document.

        Updates the appropriate field, marks the document as fixed,
        and triggers retry.

        Returns:
            Action to close wizard and show result.
        """
        self.ensure_one()

        move = self.move_id

        # Apply fix based on selection
        if self.fix_field == "partner_ruc" and self.new_partner_ruc:
            move.partner_id.write({"l10n_py_ruc": self.new_partner_ruc})

        elif self.fix_field == "partner_doc_number" and self.new_partner_doc_number:
            move.partner_id.write({"l10n_py_doc_number": self.new_partner_doc_number})

        elif (
            self.fix_field == "partner_taxpayer_type" and self.new_partner_taxpayer_type
        ):
            move.partner_id.write(
                {"l10n_py_taxpayer_type": self.new_partner_taxpayer_type}
            )

        elif self.fix_field == "company_ruc" and self.new_company_ruc:
            move.company_id.write({"l10n_py_ruc": self.new_company_ruc})

        elif self.fix_field == "other":
            # Log for manual review
            move.message_post(
                body=self.env._(
                    "Rejection resolution requires manual review. Notes: %(notes)s",
                    notes=self.notes or "",
                ),
                message_type="comment",
            )
            move.write({"l10n_py_reject_fixed": True})
            return {"type": "ir.actions.act_window_close"}

        # Mark as fixed and retry
        move.write(
            {
                "l10n_py_reject_fixed": True,
                "l10n_py_reject_fix_field": self.fix_field,
            }
        )

        try:
            move.action_retry_after_fix()
            return {
                "type": "ir.actions.act_window_close",
                "infos": {
                    "title": self.env._("Success"),
                    "message": self.env._(
                        "Document %(name)s was retried successfully.", name=move.name
                    ),
                    "type": "success",
                },
            }
        except Exception as e:
            return {
                "type": "ir.actions.act_window_close",
                "infos": {
                    "title": self.env._("Retry Failed"),
                    "message": str(e),
                    "type": "danger",
                },
            }

    def action_view_document(self) -> dict:
        """Open the rejected document.

        Returns:
            Action to open the account.move form.
        """
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }
