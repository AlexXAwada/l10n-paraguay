# l10n_py_account/models/account_move.py

from num2words import num2words

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.constrains("state", "l10n_latam_document_type_id")
    def _check_l10n_latam_documents(self):
        """Skip LATAM document validation during module installation.

        Demo invoices from standard account are posted by try_loading without
        document numbers, causing ValidationError. This is expected behavior
        in all LATAM localizations - skip during installation.
        """
        if not self.env.registry.ready:
            return
        return super()._check_l10n_latam_documents()

    # ============== PARAGUAY ACCOUNTING FIELDS ==============

    l10n_py_authorization_id = fields.Many2one(
        "account.authorization",
        string="Authorization",
        domain=(
            "[('company_id', '=', company_id), "
            "('active', '=', True), "
            "('state', '!=', 'expired')]"
        ),
        help="Authorization used for this invoice",
    )

    l10n_py_invoice_number = fields.Integer(
        string="Invoice Number",
        help="Invoice number according to authorized authorization",
    )

    l10n_py_full_invoice_number = fields.Char(
        string="Full Number",
        compute="_compute_l10n_py_full_invoice_number",
        store=True,
        help="Complete invoice number (format: 001-001-0000001)",
    )

    # ============== VAT BREAKDOWN FIELDS (SIFEN) ==============

    l10n_py_amount_subtotal_10 = fields.Monetary(
        string="Gross 10% (F005)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Gross subtotal 10% — price including tax (SIFEN F005)",
    )

    l10n_py_amount_iva_10 = fields.Monetary(
        string="VAT 10% (F016)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="VAT 10% liquidation (SIFEN F016)",
    )

    l10n_py_amount_subtotal_5 = fields.Monetary(
        string="Gross 5% (F004)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Gross subtotal 5% — price including tax (SIFEN F004)",
    )

    l10n_py_amount_iva_5 = fields.Monetary(
        string="VAT 5% (F015)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="VAT 5% liquidation (SIFEN F015)",
    )

    l10n_py_amount_exempt = fields.Monetary(
        string="Exempt Total (F003)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Exempt/un taxed subtotal (SIFEN F003)",
    )

    l10n_py_amount_iva_total = fields.Monetary(
        string="Total VAT (F014)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Total VAT liquidation (SIFEN F014)",
    )

    l10n_py_base_10 = fields.Monetary(
        string="Tax Base 10% (F019)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Net tax base 10% without VAT (SIFEN F019)",
    )

    l10n_py_base_5 = fields.Monetary(
        string="Tax Base 5% (F018)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Net tax base 5% without VAT (SIFEN F018)",
    )

    l10n_py_base_total = fields.Monetary(
        string="Total Tax Base (F020)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Total tax base (SIFEN F020 = F018 + F019)",
    )

    l10n_py_total_operation = fields.Monetary(
        string="Operation Total (F008)",
        compute="_compute_l10n_py_iva",
        store=True,
        currency_field="currency_id",
        help="Total operation amount (SIFEN F008 = F003 + F004 + F005)",
    )

    # ============== PYG EXCHANGE RATE FIELDS ==============

    l10n_py_exchange_rate = fields.Float(
        string="Exchange Rate",
        digits=(16, 4),
        help="Exchange rate to guaranies (PYG) for foreign currency invoicing",
    )

    l10n_py_amount_total_pyg = fields.Monetary(
        string="Total in Guaranies (F023)",
        compute="_compute_l10n_py_total_pyg",
        store=True,
        currency_field="currency_id",
        help="Operation total in guaranies (SIFEN F023)",
    )

    l10n_py_amount_total_words = fields.Char(
        string="Total in Words",
        compute="_compute_l10n_py_amount_total_words",
    )

    _l10n_py_invoice_unique = models.Constraint(
        "unique(l10n_py_authorization_id, l10n_py_invoice_number)",
        "Invoice number must be unique per authorization.",
    )

    # ============== ACTION METHODS ==============

    def action_post(self):
        """Override to assign sequential numbering on confirmation"""
        for move in self:
            if (
                move.move_type in ("out_invoice", "out_refund")
                and move.company_id.country_id.code == "PY"
                and move.journal_id.l10n_latam_use_documents
                and move.l10n_latam_document_type_id
            ):
                if not move.l10n_py_authorization_id:
                    if not self.env.registry.ready:
                        # Skip during installation/demo (generic invoices
                        # created by account.chart.template.try_loading)
                        continue
                    raise UserError(
                        self.env._(
                            "You must select an authorization to confirm "
                            "a sales invoice."
                        )
                    )
                if not move.l10n_py_invoice_number:
                    auth = move.l10n_py_authorization_id
                    auth.check_validity()
                    # Flush pending writes so the SQL query sees all data
                    self.env["account.move"].flush_model(["l10n_py_invoice_number"])
                    # Lock the authorization row to prevent concurrent number assignment
                    self.env.cr.execute(
                        "SELECT id FROM account_authorization WHERE id = %s FOR UPDATE",
                        (auth.id,),
                    )
                    # Query next number directly to avoid ORM cache issues
                    self.env.cr.execute(
                        """
                        SELECT COALESCE(MAX(l10n_py_invoice_number), 0)
                        FROM account_move
                        WHERE l10n_py_authorization_id = %s
                          AND l10n_py_invoice_number > 0
                          AND move_type IN ('out_invoice', 'out_refund')
                        """,
                        (auth.id,),
                    )
                    max_num = self.env.cr.fetchone()[0]
                    next_num = max_num + 1 if max_num else auth.invoice_number_from
                    if next_num > auth.invoice_number_to:
                        raise UserError(
                            self.env._(
                                "The number range is exhausted "
                                "for authorization %(timbrado)s.",
                                timbrado=auth.name,
                            )
                        )
                    auth.check_number_available(next_num, exclude_move_id=move.id)
                    move.l10n_py_invoice_number = next_num
        return super().action_post()

    # ============== COMPUTE METHODS ==============

    @api.depends(
        "l10n_py_authorization_id",
        "l10n_py_invoice_number",
    )
    def _compute_l10n_py_full_invoice_number(self):
        """Compute complete invoice number (format: 001-001-0000001)"""
        for move in self:
            if move.l10n_py_authorization_id and move.l10n_py_invoice_number:
                auth = move.l10n_py_authorization_id
                number_str = str(move.l10n_py_invoice_number).zfill(7)
                move.l10n_py_full_invoice_number = (
                    f"{auth.establishment}-{auth.expedition_point}-{number_str}"
                )
            else:
                move.l10n_py_full_invoice_number = False

    @api.depends(
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.price_total",
        "invoice_line_ids.tax_ids",
    )
    def _compute_l10n_py_iva(self):
        """Compute VAT breakdown per SIFEN v150 formula.

        SIFEN formula: base = price_total / (1 + rate/100)
                        vat  = price_total - base
        """
        for move in self:
            subtotal_10 = iva_10 = base_10 = 0.0
            subtotal_5 = iva_5 = base_5 = 0.0
            exempt = 0.0

            for line in move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            ):
                tax_rate = 0
                for tax in line.tax_ids:
                    if tax.amount == 10:
                        tax_rate = 10
                    elif tax.amount == 5:
                        tax_rate = 5

                if tax_rate == 10:
                    base = line.price_total / 1.1
                    subtotal_10 += line.price_total  # F005
                    iva_10 += line.price_total - base  # F016
                    base_10 += base  # F019
                elif tax_rate == 5:
                    base = line.price_total / 1.05
                    subtotal_5 += line.price_total  # F004
                    iva_5 += line.price_total - base  # F015
                    base_5 += base  # F018
                else:
                    exempt += line.price_subtotal  # F003

            move.l10n_py_amount_subtotal_10 = subtotal_10
            move.l10n_py_amount_iva_10 = iva_10
            move.l10n_py_base_10 = base_10
            move.l10n_py_amount_subtotal_5 = subtotal_5
            move.l10n_py_amount_iva_5 = iva_5
            move.l10n_py_base_5 = base_5
            move.l10n_py_amount_exempt = exempt
            move.l10n_py_amount_iva_total = iva_10 + iva_5  # F014
            move.l10n_py_base_total = base_10 + base_5  # F020
            move.l10n_py_total_operation = exempt + subtotal_5 + subtotal_10  # F008

    @api.depends("amount_total", "l10n_py_exchange_rate")
    def _compute_l10n_py_total_pyg(self):
        """Compute total in guaranies (F023) for foreign currency invoices"""
        for move in self:
            if move.l10n_py_exchange_rate and move.l10n_py_exchange_rate > 0:
                move.l10n_py_amount_total_pyg = (
                    move.amount_total * move.l10n_py_exchange_rate
                )
            else:
                move.l10n_py_amount_total_pyg = 0.0

    @api.depends("amount_total", "currency_id")
    def _compute_l10n_py_amount_total_words(self):
        """Convert total to words in Spanish"""
        # Map of Spanish names for common currencies in Paraguay
        _CURRENCY_NAMES_ES = {
            "PYG": "guaranies",
            "USD": "dolares americanos",
            "BRL": "reales",
            "EUR": "euros",
            "ARS": "pesos argentinos",
        }
        for move in self:
            if move.amount_total:
                currency_code = move.currency_id.name or ""
                currency_name = _CURRENCY_NAMES_ES.get(
                    currency_code,
                    move.currency_id.currency_unit_label or "guaranies",
                )
                amount_int = int(move.amount_total)
                decimal_places = move.currency_id.decimal_places
                if decimal_places > 0:
                    cents = round(
                        (move.amount_total - amount_int) * (10**decimal_places)
                    )
                    amount_words = num2words(amount_int, lang="es")
                    if cents:
                        cents_words = num2words(cents, lang="es")
                        cents_label = (
                            move.currency_id.currency_subunit_label or "centavos"
                        )
                        words = (
                            f"{amount_words} {currency_name} "
                            f"con {cents_words} {cents_label}"
                        )
                    else:
                        words = f"{amount_words} {currency_name}"
                else:
                    words = f"{num2words(amount_int, lang='es')} {currency_name}"
                move.l10n_py_amount_total_words = words.capitalize()
            else:
                move.l10n_py_amount_total_words = False

    # ============== CONSTRAINT METHODS ==============

    @api.constrains("l10n_py_authorization_id", "l10n_py_invoice_number")
    def _check_authorization_number(self):
        """Validate that invoice number is within authorized range"""
        for move in self:
            if move.l10n_py_authorization_id and move.l10n_py_invoice_number:
                move.l10n_py_authorization_id.check_number_available(
                    move.l10n_py_invoice_number,
                    exclude_move_id=move.id,
                )

    @api.constrains("l10n_py_authorization_id")
    def _check_authorization_validity(self):
        """Validate that authorization is current"""
        for move in self:
            if move.state == "posted" and move.l10n_py_authorization_id:
                move.l10n_py_authorization_id.check_validity()

    # ============== ONCHANGE METHODS ==============

    @api.onchange("l10n_py_authorization_id")
    def _onchange_authorization_id(self):
        """Clear number when changing authorization — assigned in action_post"""
        if self.l10n_py_authorization_id:
            self.l10n_py_invoice_number = 0
