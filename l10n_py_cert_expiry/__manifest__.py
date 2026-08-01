{
    "name": "Certificate Expiry Notifications",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Notify users when SIFEN certificates are about to expire",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_sifen"],
    "data": [
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "auto_install": False,
}
