# l10n_py_edi_base/models/l10n_py_transport.py

from odoo import fields, models


class Transport(models.Model):
    """Goods transport data (Grupo G SIFEN)."""

    _name = "l10n_py.transport"
    _description = "Goods Transport"

    move_id = fields.Many2one(
        "account.move",
        string="Document",
        required=True,
        ondelete="cascade",
    )

    transport_mode = fields.Selection(
        [
            ("1", "Land"),
            ("2", "River"),
            ("3", "Air"),
            ("4", "Multimodal"),
        ],
        string="Modalidad de Transport (E901)",
        required=True,
        default="1",
    )

    transport_type = fields.Selection(
        [("1", "Propio"), ("2", "Third party")],
        string="Tipo de Transport (E903)",
    )

    freight_responsibility = fields.Selection(
        [
            ("1", "Electronic Invoice Issuer"),
            ("2", "Electronic Invoice Receiver"),
            ("3", "Third party"),
            ("4", "Agente intermediario del transporte"),
        ],
        string="Responsable del Flete (E905)",
    )

    incoterm = fields.Selection(
        [
            ("CFR", "CFR"),
            ("CIF", "CIF"),
            ("CIP", "CIP"),
            ("CPT", "CPT"),
            ("DAP", "DAP"),
            ("DAT", "DAT"),
            ("DDP", "DDP"),
            ("EXW", "EXW"),
            ("FAS", "FAS"),
            ("FCA", "FCA"),
            ("FOB", "FOB"),
        ],
        string="Negotiation Condition (E906)",
    )

    manifest_number = fields.Char(
        string="Number de Manifest / Conocimiento (E907)",
    )

    transport_start_date = fields.Date(
        string="Date Inicio Transport (E909)",
    )

    transport_end_date = fields.Date(
        string="Date Fin Transport (E910)",
    )

    # Departure point (gCamSal)
    departure_address = fields.Char(
        string="Address de Salida (E920)",
    )
    departure_house = fields.Integer(
        string="Number de Casa Salida (E921)",
    )
    departure_department = fields.Integer(
        string="State/Province Salida (E924)",
    )
    departure_district = fields.Integer(
        string="Distrito Salida (E926)",
    )
    departure_city = fields.Integer(
        string="City Salida (E928)",
    )

    # Transportr data (gCamTrans)
    transporter_nature = fields.Selection(
        [("1", "Taxpayer"), ("2", "No contribuyente")],
        string="Naturaleza del Carrier (E940)",
    )
    transporter_name = fields.Char(
        string="Name del Carrier (E941)",
    )
    transporter_ruc = fields.Char(
        string="RUC del Carrier (E942)",
    )
    transporter_dv = fields.Char(
        string="DV del Carrier (E943)",
        size=1,
    )
    driver_doc_number = fields.Char(
        string="Doc. del Driver (E950)",
    )
    driver_name = fields.Char(
        string="Name del Driver (E951)",
    )

    # Related vehicles and deliveries
    vehicle_ids = fields.One2many(
        "l10n_py.transport.vehicle",
        "transport_id",
        string="Vehicles",
    )
    delivery_ids = fields.One2many(
        "l10n_py.transport.delivery",
        "transport_id",
        string="Entregas",
    )

    company_id = fields.Many2one(
        related="move_id.company_id",
        store=True,
    )


class TransportVehicle(models.Model):
    """Vehicle de transporte (gVehTras)."""

    _name = "l10n_py.transport.vehicle"
    _description = "Vehicle de Transport"

    transport_id = fields.Many2one(
        "l10n_py.transport",
        string="Transport",
        required=True,
        ondelete="cascade",
    )

    vehicle_type = fields.Char(
        string="Tipo de Vehicle (E960)",
        required=True,
    )
    brand = fields.Char(
        string="Marca (E961)",
        required=True,
    )
    plate_number = fields.Char(
        string="Identification Number (E962)",
        required=True,
    )


class TransportDelivery(models.Model):
    """Goods delivery point (gCamEnt)."""

    _name = "l10n_py.transport.delivery"
    _description = "Punto de Entrega"

    transport_id = fields.Many2one(
        "l10n_py.transport",
        string="Transport",
        required=True,
        ondelete="cascade",
    )

    address = fields.Char(
        string="Address de Entrega (E930)",
        required=True,
    )
    house_number = fields.Integer(
        string="Number de Casa (E931)",
    )
    department = fields.Integer(
        string="State/Province (E934)",
        required=True,
    )
    district = fields.Integer(
        string="Distrito (E936)",
    )
    city = fields.Integer(
        string="City (E938)",
        required=True,
    )
