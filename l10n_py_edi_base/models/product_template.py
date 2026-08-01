# l10n_py_edi_base/models/product_template.py

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ============== CAMPOS EDI PARAGUAY ==============

    l10n_py_ncm_code = fields.Char(
        string="NCM Code", size=8, help="Common Mercosur Nomenclature (8 digits)"
    )

    l10n_py_unit_code = fields.Integer(
        string="Code Unidad de Medida",
        default=77,
        help="Measurement unit code per SET (77 = UNI - Unit)",
    )
