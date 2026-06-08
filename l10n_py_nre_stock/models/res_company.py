# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Company extension for NRE warehouse configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import fields, models

if TYPE_CHECKING:
    pass


class ResCompany(models.Model):
    """Add warehouse fields for NRE stock picking."""

    _inherit = "res.company"

    l10n_py_default_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Default Source Warehouse",
        help="Default warehouse for NRE stock transfers (source location)",
    )

    l10n_py_default_dest_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Default Destination Warehouse",
        help="Default destination warehouse for NRE stock transfers",
    )
