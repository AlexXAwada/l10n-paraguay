# l10n_py_edi_base/models/l10n_py_associated_document.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AssociatedDocument(models.Model):
    """Document Associated (Grupo H del SIFEN v150).

    Allows linking reference documents to electronic invoices:
    - Electronic: referencia por CDC (44 digits)
    - Printed: referencia por timbrado/establishment/point/number
    - Electronic Certificate: tipo y number de constancia
    """

    _name = "l10n_py.associated.document"
    _description = "Document Associated (Grupo H SIFEN)"
    _order = "id"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
        index=True,
    )

    association_type = fields.Selection(
        [
            ("1", "Electronic"),
            ("2", "Printed"),
            ("3", "Electronic Certificate"),
        ],
        string="Association Type (H002)",
        required=True,
    )

    # === Electronic (H004) ===
    cdc = fields.Char(
        string="CDC",
        size=44,
        help="Code de Control del Document Electronic (44 digits)",
    )

    # === Printed (H005-H012) ===
    timbrado = fields.Char(
        size=8,
        help="Number de timbrado del documento impreso (H005)",
    )

    establishment = fields.Char(
        string="Establishment",
        size=3,
        help="Code de establishment (H006)",
    )

    expedition_point = fields.Char(
        string="Expedition Point",
        size=3,
        help="Punto de expedition (H007)",
    )

    doc_number = fields.Char(
        string="Number de Document",
        size=7,
        help="Number del documento (H008)",
    )

    doc_type_code = fields.Selection(
        [
            ("1", "Invoice"),
            ("2", "Credit Note"),
            ("3", "Debit Note"),
            ("4", "Remission Note"),
            ("5", "Withholding receipt"),
        ],
        string="Document Type Printed (H009)",
    )

    doc_date = fields.Date(
        string="Date del Document (H010)",
    )

    # === Electronic Certificate (H011-H012) ===
    constancia_type = fields.Selection(
        [
            ("1", "Constancia de no ser contribuyente"),
            ("2", "Constancia de microproductor"),
        ],
        string="Tipo de Constancia (H011)",
    )

    constancia_number = fields.Char(
        string="Number de Constancia (H012)",
        size=20,
    )

    # ============== CONSTRAINTS ==============

    @api.constrains("association_type", "cdc")
    def _check_electronic_fields(self):
        """Electronic requiere CDC; impreso/constancia no permiten CDC."""
        for rec in self:
            if rec.association_type == "1":
                if not rec.cdc:
                    raise ValidationError(
                        self.env._("Electronic document: CDC is mandatory.")
                    )
                if rec.cdc and (len(rec.cdc) != 44 or not rec.cdc.isdigit()):
                    raise ValidationError(
                        self.env._("CDC must contain exactly 44 numeric digits.")
                    )
            else:
                if rec.cdc:
                    raise ValidationError(
                        self.env._("Only electronic documents can have CDC.")
                    )

    @api.constrains(
        "association_type",
        "timbrado",
        "establishment",
        "expedition_point",
        "doc_number",
        "doc_type_code",
        "doc_date",
    )
    def _check_printed_fields(self):
        """Printed requires all fields; electronic/certificate does not allow."""
        printed_fields = {
            "timbrado": "Authorization Number",
            "establishment": "Establishment",
            "expedition_point": "Expedition Point",
            "doc_number": "Number de Document",
            "doc_type_code": "Document Type",
            "doc_date": "Date del Document",
        }
        for rec in self:
            if rec.association_type == "2":
                missing = [
                    label
                    for field_name, label in printed_fields.items()
                    if not getattr(rec, field_name)
                ]
                if missing:
                    raise ValidationError(
                        self.env._(
                            "Document impreso: campos obligatorios "
                            "faltantes: %(fields)s",
                            fields=", ".join(missing),
                        )
                    )
            elif rec.association_type in ("1", "3"):
                has_printed = any(
                    getattr(rec, f) for f in printed_fields if f != "doc_date"
                )
                if has_printed:
                    raise ValidationError(
                        self.env._(
                            "Electronic documents or certificates do not "
                            "pueden tener campos de documento impreso."
                        )
                    )

    @api.constrains("association_type", "constancia_type", "constancia_number")
    def _check_constancia_fields(self):
        """Constancia requiere tipo y number; otros tipos no permiten."""
        for rec in self:
            if rec.association_type == "3":
                if not rec.constancia_type or not rec.constancia_number:
                    raise ValidationError(
                        self.env._(
                            "Electronic certificate: type and number are mandatory."
                        )
                    )
            else:
                if rec.constancia_type or rec.constancia_number:
                    raise ValidationError(
                        self.env._(
                            "Only electronic certificates can have "
                            "tipo y number de constancia."
                        )
                    )
