# Copyright 2024 Odoo Community Association (OCA)
# License LGPL-3. See http://www.gnu.org/licenses/lgpl.html.

{
    "name": "EDI Batch Sending",
    "version": "19.0.1.0.0",
    "category": "Localization/Paraguay",
    "summary": "Batch sending and queue management for EDI documents",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-paraguay",
    "license": "LGPL-3",
    "depends": ["l10n_py_edi_base", "l10n_py_edi_sifen"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/batch_job_views.xml",
        "wizard/batch_send_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
