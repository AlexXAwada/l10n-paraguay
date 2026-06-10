# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Account Move extension for NRE → Stock Picking integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odoo import api, fields, models
from odoo.exceptions import UserError

if TYPE_CHECKING:
    pass


class AccountMove(models.Model):
    """Extension of account.move for NRE picking integration."""

    _inherit = "account.move"

    l10n_py_stock_picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="l10n_py_nre_id",
        string="Stock Pickings",
        copy=False,
        readonly=True,
    )

    l10n_py_stock_picking_count = fields.Integer(
        compute="_compute_stock_picking_count",
        string="Picking Count",
    )

    l10n_py_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Source Warehouse",
        compute="_compute_nre_warehouse",
        store=True,
        help="Warehouse where the NRE originates (stock source)",
    )

    l10n_py_dest_warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Destination Warehouse",
        compute="_compute_nre_warehouse",
        store=True,
        help="Warehouse receiving the goods",
    )

    @api.depends("l10n_latam_document_type_id.code")
    def _compute_nre_warehouse(self) -> None:
        """Compute warehouse for NRE documents."""
        for rec in self:
            if rec.l10n_latam_document_type_id.code == "7":
                rec.l10n_py_warehouse_id = rec.company_id.l10n_py_default_warehouse_id
                rec.l10n_py_dest_warehouse_id = (
                    rec.company_id.l10n_py_default_dest_warehouse_id
                )
            else:
                rec.l10n_py_warehouse_id = False
                rec.l10n_py_dest_warehouse_id = False

    @api.depends("l10n_py_stock_picking_ids")
    def _compute_stock_picking_count(self) -> None:
        """Compute number of linked pickings."""
        for rec in self:
            rec.l10n_py_stock_picking_count = len(rec.l10n_py_stock_picking_ids)

    def action_create_stock_picking(self) -> dict:
        """Create stock picking from NRE.

        Creates a stock.picking for the warehouse transfer based on
        the NRE lines. Only works for NRE documents (type 7).

        Returns:
            Action to open the created picking.
        """
        self.ensure_one()

        if self.l10n_latam_document_type_id.code != "7":
            raise UserError(
                self.env._(
                    "Stock picking can only be created for NRE documents (type 7)."
                )
            )

        if self.l10n_py_stock_picking_ids:
            raise UserError(
                self.env._(
                    "A stock picking already exists for this NRE. "
                    "View it using the 'Stock Pickings' button."
                )
            )

        if not self.l10n_py_warehouse_id:
            raise UserError(
                self.env._(
                    "No source warehouse configured. "
                    "Set l10n_py_default_warehouse_id on the company."
                )
            )

        picking_vals = {
            "partner_id": self.partner_id.id,
            "origin": self.name,
            "picking_type_id": self.l10n_py_warehouse_id.out_type_id.id,
            "location_id": self.l10n_py_warehouse_id.lot_stock_id.id,
            "location_dest_id": (
                self.l10n_py_dest_warehouse_id.lot_stock_id.id
                if self.l10n_py_dest_warehouse_id
                else self.partner_id.property_stock_customer.id
            ),
            "l10n_py_nre_id": self.id,
        }

        picking = self.env["stock.picking"].create(picking_vals)

        for inv_line in self.invoice_line_ids.filtered(
            lambda il: il.product_id and il.product_id.type != "service"
        ):
            self.env["stock.move"].create(
                {
                    "picking_id": picking.id,
                    "product_id": inv_line.product_id.id,
                    "product_uom_qty": inv_line.quantity,
                    "product_uom": inv_line.product_id.uom_id.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                }
            )

        picking.action_confirm()

        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": picking.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_stock_pickings(self) -> dict:
        """Show linked stock pickings.

        Returns:
            Action to view the pickings list.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Stock Pickings"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("l10n_py_nre_id", "=", self.id)],
            "context": {"default_l10n_py_nre_id": self.id},
        }
