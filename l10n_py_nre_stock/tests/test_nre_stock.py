# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Tests for NRE Stock Picking integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odoo.addons.account.models.account_move import AccountMove

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestNRStockPicking(TransactionCase):
    """Test NRE → Stock Picking integration."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test data."""
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
            }
        )

        cls.warehouse = cls.env["stock.warehouse"].create(
            {
                "name": "Test Warehouse",
                "code": "TWH",
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TJ",
                "type": "sale",
                "company_id": cls.env.company.id,
            }
        )

        cls.env["l10n_latam.document.type"].search(
            [
                ("code", "=", "7"),
                ("country_id", "=", cls.env.ref("base.py").id),
            ],
            limit=1,
        )

        cls.env.company.write(
            {
                "l10n_py_default_warehouse_id": cls.warehouse.id,
            }
        )

    def _create_nre(self) -> AccountMove:
        """Helper to create an NRE invoice."""
        nre_type = self.env["l10n_latam.document.type"].search(
            [
                ("code", "=", "7"),
            ],
            limit=1,
        )
        return (
            self.env["account.move"]
            .with_context(
                skip_account_move_synchronization=True,
            )
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_date": fields.Date.today(),
                    "journal_id": self.journal.id,
                    "l10n_latam_document_type_id": nre_type.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "name": self.product.name,
                                "quantity": 10.0,
                                "price_unit": 100.0,
                                "tax_ids": [(5, 0, 0)],
                            },
                        ),
                    ],
                }
            )
        )

    def test_01_nre_warehouse_computed(self) -> None:
        """NRE documents auto-compute warehouse from company."""
        nre = self._create_nre()
        self.assertEqual(nre.l10n_py_warehouse_id, self.warehouse)

    def test_02_non_nre_no_warehouse(self) -> None:
        """Non-NRE documents have no warehouse assigned."""
        invoice = (
            self.env["account.move"]
            .with_context(
                skip_account_move_synchronization=True,
            )
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_date": fields.Date.today(),
                    "journal_id": self.journal.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "name": self.product.name,
                                "quantity": 1.0,
                                "price_unit": 50.0,
                                "tax_ids": [(5, 0, 0)],
                            },
                        ),
                    ],
                }
            )
        )
        self.assertFalse(invoice.l10n_py_warehouse_id)

    def test_03_create_stock_picking_from_nre(self) -> None:
        """Create stock picking from NRE document."""
        nre = self._create_nre()
        action = nre.action_create_stock_picking()

        self.assertEqual(action["res_model"], "stock.picking")
        picking = self.env["stock.picking"].browse(action["res_id"])

        self.assertEqual(picking.l10n_py_nre_id, nre)
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(picking.move_ids.product_id, self.product)
        self.assertEqual(picking.move_ids.product_uom_qty, 10.0)

    def test_04_cannot_create_picking_twice(self) -> None:
        """Cannot create two pickings for the same NRE."""
        nre = self._create_nre()
        nre.action_create_stock_picking()

        with self.assertRaises(UserError) as ctx:
            nre.action_create_stock_picking()

        self.assertIn("already exists", str(ctx.exception.args))

    def test_05_view_stock_pickings(self) -> None:
        """View linked pickings action."""
        nre = self._create_nre()
        nre.action_create_stock_picking()

        action = nre.action_view_stock_pickings()

        self.assertEqual(action["res_model"], "stock.picking")
        self.assertEqual(action["domain"], [("l10n_py_nre_id", "=", nre.id)])

    def test_06_picking_count_computed(self) -> None:
        """Picking count is correctly computed."""
        nre = self._create_nre()
        self.assertEqual(nre.l10n_py_stock_picking_count, 0)

        nre.action_create_stock_picking()
        nre.invalidate_recordset()

        self.assertEqual(nre.l10n_py_stock_picking_count, 1)

    def test_07_stock_picking_nre_fields(self) -> None:
        """Stock picking shows NRE fields."""
        nre = self._create_nre()
        nre.action_create_stock_picking()

        picking = nre.l10n_py_stock_picking_ids[0]
        self.assertEqual(picking.l10n_py_nre_id, nre)
        # CDC is only set after sending to SIFEN, so it's empty in test
        self.assertFalse(picking.l10n_py_nre_cdc)
