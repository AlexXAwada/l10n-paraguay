# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import fields, models

if TYPE_CHECKING:
    pass


class BatchRetryWizard(models.TransientModel):
    """Wizard to retry multiple rejected documents."""

    _name = "l10n_py.edi.batch.retry.wizard"
    _description = "Batch Retry Rejected Documents"

    rejected_ids = fields.Many2many(
        comodel_name="account.move",
        string="Rejected Documents",
        domain=[("l10n_py_edi_status", "=", "rejected")],
    )

    fix_type = fields.Selection(
        selection=[
            ("all", "Retry All (no changes)"),
            ("ruc", "Fix RUC on All"),
            ("type", "Fix Taxpayer Type on All"),
        ],
        string="Fix Type",
        required=True,
        default="all",
        help="Select fix type for all documents",
    )

    new_ruc = fields.Char(
        string="Replacement RUC",
        help="RUC to set on all selected partner",
    )

    new_taxpayer_type = fields.Selection(
        selection=[
            ("1", "Taxpayer (has RUC)"),
            ("2", "Non-Taxpayer (no RUC)"),
        ],
        string="Replacement Taxpayer Type",
    )

    dry_run = fields.Boolean(
        string="Preview Only",
        default=False,
        help="If checked, shows what would be changed without applying",
    )

    def action_preview(self) -> dict:
        """Show what would be changed without applying.

        Returns:
            Tree view of documents and proposed changes.
        """
        domain = [("l10n_py_edi_status", "=", "rejected")]

        if self.env.context.get("active_ids"):
            domain = [("id", "in", self.env.context["active_ids"])]

        docs = self.env["account.move"].search(domain)

        changes = []
        for doc in docs:
            partner = doc.partner_id
            change = {
                "document": doc.name,
                "partner": partner.name,
                "current_ruc": partner.l10n_py_ruc or "None",
                "current_type": partner.l10n_py_taxpayer_type or "None",
                "proposed_ruc": self.new_ruc
                if self.fix_type == "ruc"
                else partner.l10n_py_ruc,
                "proposed_type": (
                    self.new_taxpayer_type
                    if self.fix_type == "type"
                    else partner.l10n_py_taxpayer_type
                ),
            }
            changes.append(change)

        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Proposed Changes"),
            "res_model": "ir.actions.act_window",
            "view_mode": "tree",
            "target": "new",
        }

    def action_apply_batch(self) -> dict:
        """Apply fixes and retry all selected documents.

        Returns:
            Summary of success/failure counts.
        """
        from odoo.exceptions import UserError

        if not self.rejected_ids:
            raise UserError(self.env._("No rejected documents selected."))

        success = 0
        failed = 0

        for move in self.rejected_ids:
            try:
                # Apply batch fix if needed
                if self.fix_type == "ruc" and self.new_ruc:
                    move.partner_id.write({"l10n_py_ruc": self.new_ruc})
                    move.write({"l10n_py_reject_fixed": True})

                elif self.fix_type == "type" and self.new_taxpayer_type:
                    move.partner_id.write(
                        {"l10n_py_taxpayer_type": self.new_taxpayer_type}
                    )
                    move.write({"l10n_py_reject_fixed": True})

                # Retry
                move.action_retry_after_fix()
                success += 1

            except Exception:
                failed += 1

        # Show summary
        message = self.env._(
            "Batch retry completed: %(success)s succeeded, %(failed)s failed.",
            success=success,
            failed=failed,
        )

        return {
            "type": "ir.actions.act_window_close",
            "infos": {
                "title": self.env._("Batch Retry Complete"),
                "message": message,
                "type": "success" if failed == 0 else "warning",
            },
        }
