# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import api, fields, models

if TYPE_CHECKING:
    pass


class AccountMove(models.Model):
    """Extension of account.move for authorization series."""

    _inherit = "account.move"

    l10n_py_series_code = fields.Char(
        string="Authorization Series",
        related="l10n_py_authorization_id.series_code",
        store=True,
        index=True,
        help="3-digit series code from the authorization",
    )

    l10n_py_is_default_series = fields.Boolean(
        string="Default Series",
        related="l10n_py_authorization_id.is_default",
        store=True,
        help="True if this authorization is the default series",
    )

    @api.onchange("l10n_py_authorization_id")
    def _onchange_authorization_series(self) -> None:
        """Update series code when authorization changes."""
        if self.l10n_py_authorization_id and self.l10n_py_authorization_id.series_code:
            self.l10n_py_series_code = self.l10n_py_authorization_id.series_code
