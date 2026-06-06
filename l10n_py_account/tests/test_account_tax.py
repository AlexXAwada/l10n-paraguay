"""Tests para los impuestos Paraguay: IVA 10%, IVA 5%, Exento.

En Paraguay el IVA se calcula sobre el precio bruto dividiendo:
- IVA 10% = precio / 11  (equivalente a ~9.0909%)
- IVA 5%  = precio / 22  (equivalente a ~4.5454%)
- Exento  = 0%

Los tests usan el motor de impuestos de Odoo para verificar el cálculo.
"""

import csv
import os

import odoo.modules as modules
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _csv_path(filename):
    """Return absolute path to a CSV file inside l10n_py data/template."""
    module_path = modules.module.get_module_path("l10n_py")
    return os.path.join(module_path, "data", "template", filename)


@tagged("post_install", "-at_install", "l10n_py")
class TestTaxTemplatesCSV(TransactionCase):
    """Tests estructurales sobre el CSV de templates de impuestos."""

    def test_csv_file_exists_and_has_header(self):
        """El archivo account.tax-py.csv existe y tiene headers correctos."""
        csv_path = _csv_path("account.tax-py.csv")
        self.assertTrue(
            os.path.exists(csv_path),
            f"Template CSV not found at {csv_path}",
        )
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            self.assertIn("id", headers)
            self.assertIn("name", headers)
            self.assertIn("amount", headers)
            self.assertIn("type_tax_use", headers)
            self.assertIn("tax_group_id", headers)
            self.assertIn("repartition_line_ids/repartition_type", headers)

    def test_csv_has_required_tax_templates(self):
        """El CSV tiene templates para IVA 10%, IVA 5% y Exento (sale y purchase)."""
        csv_path = _csv_path("account.tax-py.csv")
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        tax_rows = [r for r in rows if r.get("id", "").strip()]
        self.assertGreaterEqual(
            len(tax_rows),
            6,
            f"Should have at least 6 tax templates, got {len(tax_rows)}",
        )

        names = {r["id"]: r for r in tax_rows}
        self.assertIn("tax_py_iva_10_sale", names)
        self.assertIn("tax_py_iva_10_purchase", names)
        self.assertIn("tax_py_iva_5_sale", names)
        self.assertIn("tax_py_iva_5_purchase", names)
        self.assertIn("tax_py_exempt_sale", names)
        self.assertIn("tax_py_exempt_purchase", names)

    def test_csv_amounts_match_py_iva_rules(self):
        """Los porcentajes en CSV corresponden a precio/11 y precio/22."""
        csv_path = _csv_path("account.tax-py.csv")
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {r["id"]: r for r in reader if r.get("id", "").strip()}

        # IVA 10%: precio / 11 → (1/11)*100 = 9.090909...%
        expected_iva10 = round(100.0 / 11, 4)
        actual_iva10 = float(rows["tax_py_iva_10_sale"]["amount"])
        self.assertAlmostEqual(
            actual_iva10,
            expected_iva10,
            places=2,
            msg="IVA 10% debe ser precio/11 ≈ 9.0909%",
        )
        self.assertEqual(
            float(rows["tax_py_iva_10_purchase"]["amount"]),
            expected_iva10,
        )

        # IVA 5%: precio / 22 → (1/22)*100 = 4.5454...%
        actual_iva5 = float(rows["tax_py_iva_5_sale"]["amount"])
        theoretical = 100.0 / 22
        self.assertAlmostEqual(
            actual_iva5,
            theoretical,
            places=2,
            msg="IVA 5% debe ser 100/22 ≈ 4.5454",
        )
        # El valor exacto en CSV debe estar truncado o redondeado correctamente
        self.assertIn(
            actual_iva5,
            [4.5454, 4.5455],
            f"Valor IVA 5% debe ser 4.5454 o 4.5455, got {actual_iva5}",
        )

        # Exento: 0%
        self.assertEqual(float(rows["tax_py_exempt_sale"]["amount"]), 0.0)
        self.assertEqual(float(rows["tax_py_exempt_purchase"]["amount"]), 0.0)

    def test_csv_tax_groups_match(self):
        """Los grupos referenciados en las taxes existen en account.tax.group-py.csv."""
        csv_path = _csv_path("account.tax-py.csv")
        groups_path = _csv_path("account.tax.group-py.csv")

        with open(csv_path, newline="", encoding="utf-8") as f:
            tax_rows = {
                r["id"]: r
                for r in csv.DictReader(f)
                if r.get("id") and r.get("tax_group_id")
            }

        with open(groups_path, newline="", encoding="utf-8") as f:
            group_rows = {r["id"]: r for r in csv.DictReader(f) if r.get("id")}

        expected_groups = {
            "tax_group_iva_10",
            "tax_group_iva_5",
            "tax_group_exempt",
        }
        for tax_id, tax_row in tax_rows.items():
            group_ref = tax_row["tax_group_id"].strip()
            self.assertIn(
                group_ref,
                expected_groups,
                f"{tax_id} references unknown group '{group_ref}'",
            )
            self.assertIn(
                group_ref,
                group_rows,
                f"Group '{group_ref}' not defined in account.tax.group-py.csv",
            )


@tagged("post_install", "-at_install", "l10n_py")
class TestAccountTaxPY(TransactionCase):
    """Tests de cálculo de impuestos Paraguay usando el motor de Odoo.

    Paraguay IVA rules:
    - IVA 10% → precio / 11 = 9.0909%
    - IVA 5%  → precio / 22 = 4.5454%
    - Exento  → 0%
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env.ref("base.main_partner")
        # Buscar cuentas existentes en la DB (el chart l10n_py puede no estar instalado)
        cls.sale_account = cls.env["account.account"].browse(
            26
        )  # Product Sales (income)
        cls.purchase_account = cls.env["account.account"].browse(
            26
        )  # reuse for purchase test
        # Crear grupos de impuesto específicos para el test
        cls.tg_iva10 = cls.env["account.tax.group"].create(
            {
                "name": "IVA 10% Test",
                "country_id": cls.env.ref("base.py").id,
            }
        )
        cls.tg_iva5 = cls.env["account.tax.group"].create(
            {
                "name": "IVA 5% Test",
                "country_id": cls.env.ref("base.py").id,
            }
        )
        cls.tg_exempt = cls.env["account.tax.group"].create(
            {
                "name": "Exento Test",
                "country_id": cls.env.ref("base.py").id,
            }
        )
        # Crear taxes para test (IVA real Paraguaya: precio/11 y precio/22)
        cls.tax_iva10_sale = cls._make_tax("IVA 10%", 9.0909, "sale", cls.tg_iva10)
        cls.tax_iva10_pur = cls._make_tax(
            "IVA 10% Compra",
            9.0909,
            "purchase",
            cls.tg_iva10,
        )
        cls.tax_iva5_sale = cls._make_tax("IVA 5%", 4.5454, "sale", cls.tg_iva5)
        cls.tax_iva5_pur = cls._make_tax(
            "IVA 5% Compra", 4.5454, "purchase", cls.tg_iva5
        )
        cls.tax_exempt_sale = cls._make_tax("Exento Venta", 0.0, "sale", cls.tg_exempt)
        cls.tax_exempt_pur = cls._make_tax(
            "Exento Compra", 0.0, "purchase", cls.tg_exempt
        )

    @classmethod
    def _make_tax(cls, name, amount, tax_type, tax_group):
        return cls.env["account.tax"].create(
            {
                "name": name,
                "amount": amount,
                "amount_type": "percent",
                "type_tax_use": tax_type,
                "tax_group_id": tax_group.id,
                "invoice_repartition_line_ids": [
                    (0, 0, {"repartition_type": "base"}),
                    (0, 0, {"repartition_type": "tax"}),
                ],
                "refund_repartition_line_ids": [
                    (0, 0, {"repartition_type": "base"}),
                    (0, 0, {"repartition_type": "tax"}),
                ],
            }
        )

    def _tax_amount(self, move):
        """Extrae el monto de impuesto de una move confirmada."""
        move.action_post()
        tax_line = move.line_ids.filtered(lambda line: line.tax_line_id)
        return sum(
            tax_line.mapped(
                "credit" if move.move_type in ("out_invoice", "in_refund") else "debit"
            )
        )

    def test_iva_10_on_price_11000_is_1000(self):
        """IVA 10% sobre 11.000 Gs = 1.000 Gs (11.000 / 11 = 1.000)."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "price_unit": 11_000.0,
                            "tax_ids": [(6, 0, self.tax_iva10_sale.ids)],
                        },
                    )
                ],
            }
        )

        self.assertAlmostEqual(
            self._tax_amount(move),
            1_000.0,
            places=0,
            msg="IVA 10% sobre 11.000 = 1.000",
        )

    def test_iva_10_on_price_110_is_10(self):
        """IVA 10% sobre 110 Gs = 10 Gs."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "price_unit": 110.0,
                            "tax_ids": [(6, 0, self.tax_iva10_sale.ids)],
                        },
                    )
                ],
            }
        )

        self.assertAlmostEqual(
            self._tax_amount(move), 10.0, places=2, msg="IVA 10% sobre 110 = 10"
        )

    def test_iva_5_on_price_22000_is_1000(self):
        """IVA 5% sobre 22.000 Gs = 1.000 Gs (22.000 / 22 = 1.000)."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "price_unit": 22_000.0,
                            "tax_ids": [(6, 0, self.tax_iva5_sale.ids)],
                        },
                    )
                ],
            }
        )

        self.assertAlmostEqual(
            self._tax_amount(move),
            1_000.0,
            places=0,
            msg="IVA 5% sobre 22.000 = 1.000",
        )

    def test_iva_5_on_price_220_is_10(self):
        """IVA 5% sobre 220 Gs = 10 Gs."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "price_unit": 220.0,
                            "tax_ids": [(6, 0, self.tax_iva5_sale.ids)],
                        },
                    )
                ],
            }
        )

        self.assertAlmostEqual(
            self._tax_amount(move), 10.0, places=2, msg="IVA 5% sobre 220 = 10"
        )

    def test_exempt_generates_no_tax(self):
        """Operaciones exentas no generan impuesto."""
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test",
                            "price_unit": 100_000.0,
                            "tax_ids": [(6, 0, self.tax_exempt_sale.ids)],
                        },
                    )
                ],
            }
        )

        self.assertEqual(
            self._tax_amount(move),
            0.0,
            "Exento debe generar 0 impuesto",
        )

    def test_iva_10_purchase_generates_credit_fiscal(self):
        """IVA 10% en compra genera crédito fiscal (débito en cuenta)."""
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test purchase",
                            "price_unit": 11_000.0,
                            "tax_ids": [(6, 0, self.tax_iva10_pur.ids)],
                        },
                    )
                ],
            }
        )

        move.action_post()
        tax_line = move.line_ids.filtered(lambda line: line.tax_line_id)
        self.assertGreater(
            sum(tax_line.mapped("debit")),
            0.0,
            "IVA compra debe generar débito en cuenta de crédito fiscal",
        )
        self.assertAlmostEqual(
            sum(tax_line.mapped("debit")),
            1_000.0,
            places=0,
            msg="Crédito fiscal IVA 10% sobre 11.000 = 1.000",
        )

    def test_iva_5_purchase_credit_fiscal(self):
        """IVA 5% en compra genera crédito fiscal: 22.000 / 22 = 1.000 Gs."""
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test purchase",
                            "price_unit": 22_000.0,
                            "tax_ids": [(6, 0, self.tax_iva5_pur.ids)],
                        },
                    )
                ],
            }
        )
        move.action_post()
        tax_line = move.line_ids.filtered(lambda line: line.tax_line_id)
        self.assertGreater(
            sum(tax_line.mapped("debit")),
            0.0,
            "IVA 5% compra debe generar crédito fiscal",
        )
        self.assertAlmostEqual(
            sum(tax_line.mapped("debit")),
            1_000.0,
            places=0,
            msg="Crédito fiscal IVA 5% sobre 22.000 = 1.000",
        )

    def test_exempt_purchase_no_tax(self):
        """Compras exentas no generan crédito fiscal."""
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test exempt purchase",
                            "price_unit": 100_000.0,
                            "tax_ids": [(6, 0, self.tax_exempt_pur.ids)],
                        },
                    )
                ],
            }
        )
        move.action_post()
        tax_line = move.line_ids.filtered(lambda line: line.tax_line_id)
        self.assertEqual(
            sum(tax_line.mapped("debit")),
            0.0,
            "Compra exenta debe generar 0 crédito fiscal",
        )
