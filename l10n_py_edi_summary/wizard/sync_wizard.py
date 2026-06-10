from __future__ import annotations

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class EDISyncWizard(models.TransientModel):
    """Manual sync interface for EDI operations."""

    _name = "l10n_py.edi.sync.wizard"
    _description = "Manual EDI Sync"

    action_type = fields.Selection(
        selection=[
            ("check_status", "Check Status"),
            ("retry", "Retry Sending"),
            ("batch_retry", "Batch Retry"),
        ],
        string="Action",
        required=True,
        default="check_status",
    )

    move_ids = fields.Many2many(
        comodel_name="account.move",
        string="Documents",
        domain=[("l10n_py_edi_status", "in", ["sent", "pending", "rejected"])],
    )

    force_recalculate_cdc = fields.Boolean(
        string="Recalculate CDC",
        default=False,
        help="If True, invalidates CDC before retry",
    )

    def action_execute(self) -> dict:
        """Execute the selected sync action."""
        self.ensure_one()

        moves = self.env["account.move"].browse(self.move_ids.ids)

        if self.action_type == "check_status":
            success = 0
            for move in moves:
                try:
                    move._check_edi_status_from_provider()
                    success += 1
                except Exception as e:
                    _logger.warning(
                        "Failed to check status for %s: %s", move.id, str(e)
                    )

        elif self.action_type == "retry":
            success = 0
            for move in moves:
                try:
                    if self.force_recalculate_cdc and move.l10n_py_cdc:
                        move.write({"l10n_py_cdc": False})
                    move.action_send_edi()
                    success += 1
                except Exception as e:
                    _logger.warning("Failed to retry for %s: %s", move.id, str(e))

        elif self.action_type == "batch_retry":
            success = 0
            # Invalidate CDCs first
            if self.force_recalculate_cdc:
                moves.filtered(lambda m: m.l10n_py_cdc).write({"l10n_py_cdc": False})
            # Reset status
            moves.filtered(lambda m: m.l10n_py_edi_status == "rejected").write(
                {"l10n_py_edi_status": "to_send"}
            )
            # Send
            for move in moves:
                try:
                    move.action_send_edi()
                    success += 1
                except Exception as e:
                    _logger.warning("Failed to batch retry for %s: %s", move.id, str(e))

        message = self.env._(
            "%(success)s of %(total)s documents processed successfully",
            success=success,
            total=len(moves),
        )

        return {
            "type": "ir.actions.act_window_close",
            "infos": {
                "title": self.env._("Sync Complete"),
                "message": message,
                "type": "success" if success == len(moves) else "warning",
            },
        }
