{
    "name": "EDI Contingency Mode",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Offline contingency mode for EDI with physical booklets",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": [
        "l10n_py_edi_base",
        "l10n_py_edi_sifen",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/contingency_booklet_views.xml",
        "views/contingency_invoice_views.xml",
        "wizard/contingency_activate_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
