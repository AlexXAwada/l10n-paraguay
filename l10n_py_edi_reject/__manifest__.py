# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

{
    "name": "EDI Reject Resolution",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Resolve rejected EDI documents and resubmit",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_base", "l10n_py_edi_sifen"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/resolve_reject_wizard_views.xml",
        "views/batch_retry_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
