# l10n_py_edi_base/models/res_company.py

from odoo import api, fields, models

from odoo.addons.l10n_py_base.validators.ruc_validator import RUCValidator


class ResCompany(models.Model):
    _inherit = "res.company"

    # ============== EDI PARAGUAY FIELDS ==============

    l10n_py_ruc = fields.Char(
        string="RUC",
        size=8,
        help="Taxpayer Unique Record sin digit check digit",
    )

    l10n_py_dv = fields.Char(
        string="DV",
        size=1,
        compute="_compute_dv",
        store=True,
        help="RUC Check Digit",
    )

    l10n_py_ruc_full = fields.Char(
        string="RUC Completo",
        compute="_compute_ruc_full",
        store=True,
        help="RUC with check digit",
    )

    l10n_py_trade_name = fields.Char(
        string="Trade Name",
        help="Commercial or trade name de la empresa",
    )

    l10n_py_economic_activity_code = fields.Char(
        string="Economic Activity Code",
        size=8,
        help="Main economic activity code per SET",
    )

    l10n_py_economic_activity = fields.Char(
        string="Economic Activity Description",
        help="Economic activity description principal",
    )

    l10n_py_webhook_token = fields.Char(
        string="Webhook Token",
        help="Token for authenticating SIFEN webhook requests",
    )

    # ============== LOCATION FIELDS (RELATED) ==============

    l10n_py_department_code = fields.Integer(
        string="Code State/Province SET",
        related="partner_id.l10n_py_department_code",
        store=True,
        readonly=True,
        help="Department code per SET",
    )

    l10n_py_district_code = fields.Integer(
        string="Code Distrito SET",
        help="District code per SET",
    )

    l10n_py_city_code = fields.Char(
        string="Code City SET",
        related="partner_id.l10n_py_city_code",
        store=True,
        readonly=True,
        help="City code per SET",
    )

    # ============== COMPUTE METHODS ==============

    @api.depends("l10n_py_ruc")
    def _compute_dv(self):
        """Calcular digit check digit del RUC"""
        for company in self:
            if not company.l10n_py_ruc:
                company.l10n_py_dv = False
                continue
            ruc_clean = company.l10n_py_ruc.replace("-", "").strip()
            if ruc_clean.isdigit() and len(ruc_clean) >= 6:
                company.l10n_py_dv = str(RUCValidator._calculate_check_digit(ruc_clean))
            else:
                company.l10n_py_dv = False

    @api.depends("l10n_py_ruc", "l10n_py_dv")
    def _compute_ruc_full(self):
        """Calcular Full RUC con DV"""
        for company in self:
            if company.l10n_py_ruc and company.l10n_py_dv:
                company.l10n_py_ruc_full = f"{company.l10n_py_ruc}-{company.l10n_py_dv}"
            else:
                company.l10n_py_ruc_full = False
