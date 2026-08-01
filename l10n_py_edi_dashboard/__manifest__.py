# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

{
    "name": "EDI Dashboard Paraguay",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Dashboard and KPIs for EDI operations",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": [
        "l10n_py_edi_base",
        "l10n_py_edi_sifen",
        "l10n_py_edi_batch",
        "l10n_py_edi_contingency",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/dashboard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
