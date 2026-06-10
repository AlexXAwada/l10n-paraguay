{
    "name": "EDI Daily Summary and Sync",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Daily EDI summary emails and manual sync interface",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/edi_summary_views.xml",
        "views/sync_wizard_views.xml",
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}
