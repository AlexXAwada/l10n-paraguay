# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    """Extension of account.move for reject resolution."""

    _inherit = "account.move"

    l10n_py_reject_code = fields.Char(
        copy=False,
        help="SIFEN error code for the rejection",
    )

    l10n_py_reject_message = fields.Text(
        copy=False,
        help="Full rejection message from SIFEN",
    )

    l10n_py_reject_action = fields.Char(
        copy=False,
        help="Suggested action to resolve the rejection",
    )

    l10n_py_reject_date = fields.Datetime(
        copy=False,
        help="When the document was rejected",
    )

    l10n_py_reject_fixed = fields.Boolean(
        default=False,
        copy=False,
        help="Set to True after applying a fix",
    )

    l10n_py_reject_fix_field = fields.Char(
        copy=False,
        help="Field name that needs to be corrected",
    )

    l10n_py_retry_count = fields.Integer(
        default=0,
        copy=False,
    )

    l10n_py_last_retry = fields.Datetime(
        copy=False,
    )

    def _process_edi_error(self, result: dict) -> None:
        """Process EDI error/response and extract rejection info.

        Override to store rejection details for resolution.
        """
        if result.get("estado") == "rejected":
            self.write(
                {
                    "l10n_py_reject_code": result.get("codigo_respuesta", ""),
                    "l10n_py_reject_message": result.get("mensaje_respuesta", ""),
                    "l10n_py_reject_date": fields.Datetime.now(),
                }
            )

            # Get actionable suggestion from connector
            connector = self._get_edi_connector()
            if connector:
                msg, action = connector._interpret_sifen_error(
                    result.get("codigo_respuesta", ""),
                    result.get("mensaje_respuesta", ""),
                )
                self.l10n_py_reject_action = action

    def action_open_reject_wizard(self) -> dict:
        """Open the reject resolution wizard.

        Returns:
            Wizard action for the selected document.
        """
        return {
            "name": self.env._("Resolve Rejection"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_py.edi.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def action_retry_after_fix(self) -> bool:
        """Retry sending after a fix was applied.

        Increments retry counter, clears CDC to force recalculation,
        and attempts to resend.

        Returns:
            True on success, raises on error.
        """
        from odoo.exceptions import UserError

        self.ensure_one()

        if self.l10n_py_edi_status != "rejected":
            raise UserError(self.env._("Only rejected documents can be retried."))

        # Clear old CDC to force recalculation
        old_cdc = self.l10n_py_cdc

        # Mark as needing retry
        self.write(
            {
                "l10n_py_cdc": False,
                "l10n_py_reject_fixed": True,
                "l10n_py_retry_count": self.l10n_py_retry_count + 1,
                "l10n_py_last_retry": fields.Datetime.now(),
                "l10n_py_edi_status": "to_send",
            }
        )

        try:
            self.action_send_edi()
            return True
        except Exception as e:
            # Revert CDC and status
            self.write(
                {
                    "l10n_py_cdc": old_cdc,
                    "l10n_py_edi_status": "rejected",
                }
            )
            raise UserError(self.env._("Retry failed: %(error)s", error=str(e))) from e

    @api.model
    def _cron_retry_pending_fixes(self) -> None:
        """Cron to retry documents where fix was applied.

        Only retries documents that:
        - Were rejected
        - Have l10n_py_reject_fixed = True
        - Have been in rejected state for more than 5 minutes
        """
        threshold = fields.Datetime.now() - fields.timedelta(minutes=5)

        pending = self.search(
            [
                ("l10n_py_edi_status", "=", "rejected"),
                ("l10n_py_reject_fixed", "=", True),
                ("l10n_py_reject_date", "<", threshold),
                ("l10n_py_retry_count", "<", 3),
            ]
        )

        for move in pending:
            try:
                move.action_retry_after_fix()
            except Exception as e:
                _logger.warning(
                    "Failed to retry document %s: %s",
                    move.name,
                    str(e),
                )
