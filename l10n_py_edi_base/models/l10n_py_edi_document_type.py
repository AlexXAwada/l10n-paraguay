# l10n_py_edi_base/models/l10n_py_edi_document_type.py

from odoo import fields, models


class EDIDocumentType(models.Model):
    """Electronic Document Types"""

    _name = "l10n_py.edi.document.type"
    _description = "Electronic Document Type"
    _order = "code"

    code = fields.Char(string="Code", required=True, size=2)
    name = fields.Char(string="Name", required=True, translate=True)
    description = fields.Text(string="Description", translate=True)

    _code_unique = models.Constraint(
        "unique(code)",
        "Document type code must be unique",
    )
