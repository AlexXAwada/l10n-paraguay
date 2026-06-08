# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Wizard to create stock picking from NRE documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import fields, models

if TYPE_CHECKING:
    pass


class CreatePickingWizard(models.TransientModel):
    """Wizard to create stock picking from NRE."""

    _name = "l10n_py_nre.create.picking.wizard"
    _description = "Create Stock Picking from NRE"

    nre_ids = fields.Many2many(
        comodel_name="account.move",
        string="NRE Documents",
        domain=[("l10n_latam_document_type_id.code", "=", "7")],
    )

    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Source Warehouse",
        required=True,
        help="Warehouse where the goods are dispatched from",
    )

    dest_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Destination Warehouse",
        help="Optional: specific destination warehouse",
    )

    def action_create_pickings(self) -> dict:
        """Create stock picking for each NRE.

        Returns:
            Action to view the created pickings.
        """
        nres = self.env["account.move"].browse(self.nre_ids.ids)
        pickings = self.env["stock.picking"]

        for nre in nres:
            vals = {
                "partner_id": nre.partner_id.id,
                "origin": nre.name,
                "picking_type_id": self.warehouse_id.out_type_id.id,
                "location_id": self.warehouse_id.lot_stock_id.id,
                "location_dest_id": (
                    self.dest_warehouse_id.lot_stock_id.id
                    if self.dest_warehouse_id
                    else nre.partner_id.property_stock_customer.id
                ),
                "l10n_py_nre_id": nre.id,
            }

            picking = self.env["stock.picking"].create(vals)

            for line in nre.invoice_line_ids.filtered(
                lambda l: l.product_id and l.product_id.type != "service"
            ):
                self.env["stock.move"].create(
                    {
                        "picking_id": picking.id,
                        "product_id": line.product_id.id,
                        "product_uom_qty": line.quantity,
                        "product_uom": line.product_id.uom_id.id,
                        "location_id": picking.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                    }
                )

            picking.action_confirm()
            pickings |= picking

        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Created Stock Pickings"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
        }
