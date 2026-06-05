# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("py")
    def _get_py_template_data(self):
        return {
            "code_digits": "8",
            "property_account_receivable_id": "account_py_301",
            "property_account_payable_id": "account_py_2001",
            "property_account_expense_categ_id": "account_py_50101_expense",
            "property_account_income_categ_id": "account_py_40101_income",
            "property_account_income_id": "account_py_40101_income",
            "property_account_expense_id": "account_py_50101_expense",
            "default_pos_receivable_account_id": "account_py_301",
            "income_currency_exchange_account_id": "account_py_805_income",
            "expense_currency_exchange_account_id": "account_py_1304_expense",
            "default_cash_difference_income_account_id": "account_py_802_income",
            "default_cash_difference_expense_account_id": "account_py_1116_expense",
            "account_journal_suspense_account_id": "account_py_103",
            "bank_account_code_prefix": "1.01.01.04",
            "cash_account_code_prefix": "1.01.01.02",
            "transfer_account_code_prefix": "1.01.01.03",
        }

    @template("py", "res.company")
    def _get_py_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.py",
                "bank_account_code_prefix": "1.01.01.04",
                "cash_account_code_prefix": "1.01.01.02",
                "transfer_account_code_prefix": "1.01.01.03",
            },
        }
