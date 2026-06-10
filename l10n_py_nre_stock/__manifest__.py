# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

{
    "name": "NRE Stock Picking Integration",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Link NRE electronic documents to stock pickings",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_base", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
