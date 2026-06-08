# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Stock Picking extension for NRE integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import fields, models

if TYPE_CHECKING:
    pass


class StockPicking(models.Model):
    """Extension of stock.picking to link with NRE documents."""

    _inherit = "stock.picking"

    l10n_py_nre_id = fields.Many2one(
        comodel_name="account.move",
        string="NRE Document",
        index=True,
        copy=False,
        help="NRE that originated this stock picking",
    )

    l10n_py_nre_cdc = fields.Char(
        related="l10n_py_nre_id.l10n_py_cdc",
        string="NRE CDC",
        store=True,
    )

    l10n_py_driver_name = fields.Char(
        string="Driver Name",
        related="l10n_py_nre_id.l10n_py_transport_id.driver_name",
        readonly=True,
    )

    l10n_py_driver_document = fields.Char(
        string="Driver Document",
        related="l10n_py_nre_id.l10n_py_transport_id.driver_doc_number",
        readonly=True,
    )
