{
    "name": "EDI Email Notifications",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Automatic email notifications for EDI documents",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_base", "mail"],
    "data": [
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}
