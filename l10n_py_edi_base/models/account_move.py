# l10n_py_edi_base/models/account_move.py

import base64 as b64
import io
import logging
import secrets
import string
import time

import qrcode
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.cdc_generator import CDCGenerator

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # ============== CAMPOS EDI PARAGUAY ==============

    l10n_py_emission_type = fields.Selection(
        [("1", "Normal"), ("2", "Contingency")],
        string="Emission Type",
        default="1",
        required=True,
    )

    l10n_py_transaction_type = fields.Selection(
        [
            ("1", "Sale of goods"),
            ("2", "Service provision"),
            ("3", "Mixed (Sale of goods and services)"),
            ("4", "Venta de activo fijo"),
            ("5", "Venta de divisas"),
            ("6", "Compra de divisas"),
            ("7", "Promotion or sample delivery"),
            ("8", "Donation"),
            ("9", "Anticipo"),
            ("10", "Compra de productos"),
            ("11", "Purchase of services"),
            ("12", "Output tax sale"),
            ("13", "Input tax purchase"),
        ],
        string="Paraguay Transaction Type",
        required=True,
        default="1",
    )

    l10n_py_presence_type = fields.Selection(
        [
            ("1", "Operation presencial"),
            ("2", "Electronic operation"),
            ("3", "Operation telemarketing"),
            ("4", "Venta a domicilio"),
            ("5", "Operation bancaria"),
        ],
        string="Tipo de Presencia",
        default="1",
    )

    # Campos de respuesta EDI
    l10n_py_cdc = fields.Char(
        "CDC",
        readonly=True,
        copy=False,
        help="Control code of the electronic document",
    )
    l10n_py_cdc_emission_date = fields.Datetime(
        "CDC Emission Date",
        readonly=True,
        copy=False,
        help=(
            "Timestamp used to generate the CDC datetime segment. "
            "Persisted on the first send attempt and reused on every "
            "retry so the CDC stays stable."
        ),
    )
    l10n_py_qr_code = fields.Binary("Code QR", readonly=True, copy=False)
    l10n_py_qr_string = fields.Char("String QR", readonly=True, copy=False)
    l10n_py_edi_xml = fields.Binary("XML Firmado", readonly=True, copy=False)
    l10n_py_edi_xml_filename = fields.Char("XML Filename", readonly=True)
    l10n_py_kude_pdf = fields.Binary("KUDE (PDF)", readonly=True, copy=False)
    l10n_py_kude_filename = fields.Char("KUDE Filename", readonly=True)

    l10n_py_edi_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_send", "To Send"),
            ("sent", "Sent"),
            ("processing", "Processing"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("error", "Error"),
        ],
        string="EDI Status",
        default="draft",
        readonly=True,
        copy=False,
    )

    l10n_py_edi_message = fields.Text("Mensaje EDI", readonly=True, copy=False)
    l10n_py_edi_batch_id = fields.Char("ID de Lote", readonly=True, copy=False)
    l10n_py_edi_accepted_date = fields.Datetime(
        string="EDI Acceptance Date",
        readonly=True,
        copy=False,
    )
    l10n_py_edi_rejected_date = fields.Datetime(
        string="EDI Rejection Date",
        readonly=True,
        copy=False,
    )
    l10n_py_security_code = fields.Char(
        "Code de Security", size=9, readonly=True, copy=False
    )
    l10n_py_receipt_id = fields.Char("Receipt ID", help="Unique customer system ID")

    # Contingency fields
    l10n_py_contingency_motive = fields.Char("Contingency Reason")

    # Documents asociados (Grupo H SIFEN)
    l10n_py_associated_document_ids = fields.One2many(
        "l10n_py.associated.document",
        "move_id",
        string="Documents Associateds",
        help="Documents asociados al DTE (Grupo H del SIFEN)",
    )

    # Operation comercial (Grupo D — gOpeCom)
    l10n_py_exchange_rate_condition = fields.Selection(
        [("1", "Global"), ("2", "Per Item")],
        string="Exchange Rate Condition",
        default="1",
        help="Exchange rate condition (D015)",
    )

    # Tipo de pago (Grupo E — gPaConEIni)
    l10n_py_payment_type = fields.Selection(
        [
            ("1", "Cash"),
            ("2", "Check"),
            ("3", "Credit card"),
            ("4", "Debit card"),
            ("5", "Transfer"),
            ("6", "Bank giro"),
            ("7", "Electronic wallet"),
            ("8", "Business card"),
            ("9", "Voucher"),
            ("10", "Withholding"),
            ("11", "Advance"),
            ("12", "Tax value"),
            ("13", "Commercial value"),
            ("14", "Compensation"),
            ("15", "Permuta"),
            ("16", "Pago bancario"),
        ],
        string="Tipo de Pago",
        default="1",
        help="Payment type for cash condition (E606)",
    )

    # AFE Fields — Electronic Self-Invoice (Grupo E — gCamAE)
    l10n_py_afe_constancia_type = fields.Selection(
        [("1", "No contribuyente"), ("2", "Microproductor")],
        string="Tipo de Constancia (EA002)",
    )
    l10n_py_afe_constancia_number = fields.Char(
        string="Number de Constancia (EA004)",
        size=20,
    )
    l10n_py_afe_constancia_control = fields.Char(
        string="Number de Control (EA005)",
        size=20,
    )
    l10n_py_afe_vendor_doc_type = fields.Selection(
        [
            ("1", "Paraguayan ID"),
            ("2", "Pasaporte"),
            ("3", "Foreign ID"),
            ("4", "Carnet de residencia"),
        ],
        string="Tipo Doc. Vendedor (EA006)",
    )
    l10n_py_afe_vendor_doc_number = fields.Char(
        string="Nro. Doc. Vendedor (EA008)",
        size=20,
    )
    l10n_py_afe_vendor_name = fields.Char(
        string="Name Vendedor (EA009)",
    )
    l10n_py_afe_vendor_address = fields.Char(
        string="Address Vendedor (EA010)",
    )
    l10n_py_afe_vendor_house = fields.Integer(
        string="Nro. Casa Vendedor (EA011)",
    )
    l10n_py_afe_vendor_department = fields.Integer(
        string="State/Province Vendedor (EA012)",
    )
    l10n_py_afe_vendor_district = fields.Integer(
        string="Distrito Vendedor (EA014)",
    )
    l10n_py_afe_vendor_city = fields.Integer(
        string="City Vendedor (EA016)",
    )
    l10n_py_afe_provision_address = fields.Char(
        string="Provision Address (EA018)",
    )
    l10n_py_afe_provision_department = fields.Integer(
        string="Provision State/Province (EA019)",
    )
    l10n_py_afe_provision_district = fields.Integer(
        string="Provision District (EA021)",
    )
    l10n_py_afe_provision_city = fields.Integer(
        string="Provision City (EA023)",
    )

    # Campo auxiliar para visibilidad en la vista
    l10n_py_doc_type_code = fields.Char(
        compute="_compute_l10n_py_doc_type_code",
    )

    # NRE Fields (Electronic Remission Note — type 7)
    l10n_py_nre_motive = fields.Selection(
        [
            ("1", "Traslado por venta"),
            ("2", "Consignment transfer"),
            ("3", "Export transfer"),
            ("4", "Import transfer"),
            ("5", "Traslado entre locales"),
            ("6", "Otros"),
        ],
        string="Remission Reason (E501)",
    )

    l10n_py_nre_estimated_invoice_date = fields.Date(
        string="Date Estimada de Billing (E506)",
        help="Estimated invoicing date for NRE without associated invoice",
    )

    # Transport (Grupo G SIFEN — NRE)
    l10n_py_transport_id = fields.Many2one(
        "l10n_py.transport",
        string="Data de Transport",
        help="Transport data for Remission Note (Grupo G SIFEN)",
    )

    # Campo prazo de transmissão
    l10n_py_transmission_deadline = fields.Datetime(
        string="Transmission Deadline",
        compute="_compute_transmission_deadline",
        store=True,
        help="Maximum deadline to transmit the DTE (72 hours from emission)",
    )

    # ============== LIFECYCLE METHODS ==============

    def action_post(self):
        """Override para configurar estado EDI al confirmar factura."""
        res = super().action_post()
        for move in self:
            if move.move_type in ("out_invoice", "out_refund"):
                move.l10n_py_edi_status = "to_send"
        return res

    @api.depends("invoice_date")
    def _compute_transmission_deadline(self):
        """Compute maximum transmission deadline (72h from emission)"""
        for move in self:
            if move.invoice_date:
                # 72 hours from start of emission day
                move.l10n_py_transmission_deadline = fields.Datetime.from_string(
                    str(move.invoice_date) + " 00:00:00"
                ) + relativedelta(hours=72)
            else:
                move.l10n_py_transmission_deadline = False

    @api.depends("l10n_latam_document_type_id")
    def _compute_l10n_py_doc_type_code(self):
        for move in self:
            move.l10n_py_doc_type_code = (
                move.l10n_latam_document_type_id.code
                if move.l10n_latam_document_type_id
                else ""
            )

    # ============== ONCHANGE METHODS ==============

    @api.onchange("invoice_line_ids")
    def _onchange_invoice_lines_transaction_type(self):
        """Auto-detect transaction type based on products"""
        if self.invoice_line_ids:
            has_products = False
            has_services = False

            for line in self.invoice_line_ids.filtered(
                lambda line: line.display_type not in ("line_section", "line_note")
            ):
                if line.product_id:
                    if line.product_id.type in ["consu", "product"]:
                        has_products = True
                    elif line.product_id.type == "service":
                        has_services = True

            if has_products and has_services:
                self.l10n_py_transaction_type = "3"  # Mixto
            elif has_services:
                self.l10n_py_transaction_type = "2"  # Servicios
            else:
                self.l10n_py_transaction_type = "1"  # Goods

    # ============== CONSTRAINT METHODS ==============

    @api.constrains("l10n_py_security_code")
    def _check_security_code(self):
        for record in self:
            if record.l10n_py_security_code and len(record.l10n_py_security_code) != 9:
                raise ValidationError(
                    self.env._("Security code must have exactly 9 characters")
                )

    # ============== PRVATTE METHODS ==============

    def _generate_security_code(self):
        """Generate security code random de 9 digits"""
        return "".join(secrets.choice(string.digits) for _ in range(9))

    @staticmethod
    def _get_country_alpha3(country):
        """Convert res.country (ISO alpha-2) to ISO alpha-3 for SIFEN PaisType."""
        if not country or not country.code:
            return "PRY"
        # Common countries for Paraguay trade; full table at ISO 3166-1
        _ALPHA2_TO_3 = {
            "PY": "PRY",
            "AR": "ARG",
            "BR": "BRA",
            "UY": "URY",
            "BO": "BOL",
            "CL": "CHL",
            "PE": "PER",
            "US": "USA",
            "CO": "COL",
            "EC": "ECU",
            "VE": "VEN",
            "MX": "MEX",
            "ES": "ESP",
            "DE": "DEU",
            "CN": "CHN",
            "JP": "JPN",
            "KR": "KOR",
            "TW": "TWN",
            "IN": "IND",
            "GB": "GBR",
            "FR": "FRA",
            "IT": "ITA",
            "PT": "PRT",
            "CA": "CAN",
        }
        return _ALPHA2_TO_3.get(country.code, country.code)

    def _prepare_edi_document_data(self):
        """Prepare electronic document data in JSON format"""
        self.ensure_one()

        if not self.l10n_py_security_code:
            self.l10n_py_security_code = self._generate_security_code()

        # Generate and persist the CDC (and the timestamp used to build it)
        # on the first send attempt so it stays stable across retries,
        # whether or not the previous attempt succeeded.
        if not self.l10n_py_cdc:
            doc_type_code = "1"
            if self.l10n_latam_document_type_id:
                doc_type_code = self.l10n_latam_document_type_id.code or "1"
            emission_date = self.l10n_py_cdc_emission_date or fields.Datetime.now()
            cdc = CDCGenerator.generate(
                company_ruc=self.company_id.l10n_py_ruc,
                doc_type=int(doc_type_code),
                establishment=(self.journal_id.l10n_py_establishment or "001"),
                expedition_point=self.journal_id.l10n_py_point or "001",
                sequence=int(self._get_edi_sequence_number()),
                emission_date=emission_date,
                security_code=self.l10n_py_security_code or None,
            )
            self.write(
                {
                    "l10n_py_cdc": cdc,
                    "l10n_py_cdc_emission_date": emission_date,
                }
            )

        # Obtener code de tipo de documento desde l10n_latam
        doc_type_code = "1"
        if self.l10n_latam_document_type_id:
            doc_type_code = self.l10n_latam_document_type_id.code or "1"

        # Data del timbrado (Grupo B)
        auth = self.l10n_py_authorization_id or self.journal_id.l10n_py_authorization_id
        timbrado_data = {}
        if auth:
            timbrado_data = {
                "timbrado": auth.name or "",
                "timbradoDateInicio": (
                    auth.date_from.strftime("%Y-%m-%d") if auth.date_from else ""
                ),
                "timbradoDateFin": (
                    auth.date_to.strftime("%Y-%m-%d") if auth.date_to else ""
                ),
            }

        # Build data structure per required format
        document_data = {
            "tipoDocumento": int(doc_type_code),
            "establecimiento": (self.journal_id.l10n_py_establishment or "001"),
            "punto": self.journal_id.l10n_py_point or "001",
            "numero": self._get_edi_sequence_number(),
            **timbrado_data,
            "descripcion": self.name or "",
            "observacion": self.narration or "",
            "fecha": (
                self.invoice_date.strftime("%Y-%m-%dT%H:%M:%S")
                if self.invoice_date
                else fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            ),
            "tipoEmision": int(self.l10n_py_emission_type),
            "tipoTransaccion": int(self.l10n_py_transaction_type),
            "tipoTax": 1,  # VAT
            "moneda": self.currency_id.name,
            "condicionTipoCambio": int(self.l10n_py_exchange_rate_condition or "1"),
            "tipoCambio": self.l10n_py_exchange_rate or 0,
            "receiptId": (self.l10n_py_receipt_id or f"{self.company_id.id}-{self.id}"),
            "codigoSecurityRandom": self.l10n_py_security_code,
            "cliente": self._prepare_customer_data(),
            "factura": {"presencia": int(self.l10n_py_presence_type)},
            "condicion": self._prepare_payment_condition(),
            "items": self._prepare_invoice_lines(),
        }

        # Agregar datos de usuario issuer si existe
        if self.user_id:
            document_data["usuario"] = {
                "documentoTipo": 1,  # ID card
                "documentoNumero": self.user_id.partner_id.vat or "",
                "nombre": self.user_id.name,
                "cargo": self.user_id.function or "Vendedor",
            }

        # Documents asociados (Grupo H)
        if self.l10n_py_associated_document_ids:
            document_data["documentosAsociados"] = self._prepare_associated_documents()

        # Campos NRE (tipo=7)
        doc_type_code = "1"
        if self.l10n_latam_document_type_id:
            doc_type_code = self.l10n_latam_document_type_id.code or "1"
        if doc_type_code == "7":
            document_data["remision"] = {
                "motivo": int(self.l10n_py_nre_motive or "1"),
            }
            if self.l10n_py_nre_estimated_invoice_date:
                document_data["remision"]["fechaEstimada"] = (
                    self.l10n_py_nre_estimated_invoice_date.strftime("%Y-%m-%d")
                )

        # AFE Fields (type=4) — Electronic Self-Invoice
        if doc_type_code == "4":
            document_data["autofactura"] = self._prepare_autofactura_data()

        # Transport (tipo=7 — NRE)
        if doc_type_code == "7" and self.l10n_py_transport_id:
            document_data["transporte"] = self._prepare_transport_data()

        # Totales SIFEN
        document_data["totales"] = {
            "totalExento": self.l10n_py_amount_exempt,  # F003
            "totalGravado5": self.l10n_py_amount_subtotal_5,  # F004
            "totalGravado10": self.l10n_py_amount_subtotal_10,  # F005
            "totalOperacion": self.l10n_py_total_operation,  # F008
            "totalIva": self.l10n_py_amount_iva_total,  # F014
            "liquidacionIva5": self.l10n_py_amount_iva_5,  # F015
            "liquidacionIva10": self.l10n_py_amount_iva_10,  # F016
            "baseGravada5": self.l10n_py_base_5,  # F018
            "baseGravada10": self.l10n_py_base_10,  # F019
            "totalBaseGravada": self.l10n_py_base_total,  # F020
        }
        if self.l10n_py_amount_total_pyg:
            document_data["totales"]["totalPYG"] = self.l10n_py_amount_total_pyg  # F023
        else:
            document_data["totales"]["totalPYG"] = document_data["totales"][
                "totalOperacion"
            ]

        document_data["cdc"] = self.l10n_py_cdc or ""
        document_data["security_code"] = self.l10n_py_security_code or ""
        document_data["emission_date"] = self.l10n_py_cdc_emission_date

        return document_data

    def _prepare_associated_documents(self):
        """Preparar datos de documentos asociados para JSON EDI."""
        docs = []
        for ad in self.l10n_py_associated_document_ids:
            doc_data = {
                "tipoAsociacion": int(ad.association_type),
            }
            if ad.association_type == "1":
                doc_data["cdc"] = ad.cdc
            elif ad.association_type == "2":
                doc_data.update(
                    {
                        "timbrado": ad.timbrado,
                        "establecimiento": ad.establishment,
                        "punto": ad.expedition_point,
                        "numero": ad.doc_number,
                        "tipoDocumentPrinted": int(ad.doc_type_code),
                        "fecha": (
                            ad.doc_date.strftime("%Y-%m-%d") if ad.doc_date else ""
                        ),
                    }
                )
            elif ad.association_type == "3":
                doc_data.update(
                    {
                        "constanciaTipo": int(ad.constancia_type),
                        "constanciaNumero": ad.constancia_number,
                    }
                )
            docs.append(doc_data)
        return docs

    def _prepare_customer_data(self):
        """Preparar datos del cliente (Grupo D receptor)"""
        partner = self.partner_id

        # iNatRec: 1=Taxpayer, 2=No Taxpayer
        nat_rec = partner.l10n_py_taxpayer_type or "1"

        # iTiOpe: 1=B2B, 2=B2C, 3=B2G, 4=B2F (extranjero)
        if partner.country_id and partner.country_id.code != "PY":
            ti_ope = "4"  # Extranjero
        elif nat_rec == "2":
            ti_ope = "2"  # B2C
        else:
            ti_ope = "1"  # B2B

        customer_data = {
            "naturalezaReceptor": nat_rec,
            "tipoOperacion": ti_ope,
            "contribuyente": nat_rec == "1",
            "ruc": partner.l10n_py_ruc or "",
            "dvReceptor": partner.l10n_py_ruc_dv or "",
            "tipoTaxpayer": "2" if partner.is_company else "1",
            "razonSocial": partner.name,
            "nombreFantasia": partner.l10n_py_fantasy_name or partner.name,
            "direccion": partner.street or "N/A",
            "numeroCasa": (
                partner.street_number if hasattr(partner, "street_number") else "0"
            )
            or "0",
            "pais": self._get_country_alpha3(partner.country_id) or "PRY",
            "paisDescripcion": partner.country_id.name or "Paraguay",
        }

        # Add location data if available
        if partner.l10n_py_department_code:
            customer_data.update(
                {
                    "departamento": partner.l10n_py_department_code,
                    "departamentoDescripcion": (
                        partner.state_id.name if partner.state_id else ""
                    ),
                    "ciudad": partner.l10n_py_city_code or "",
                    "ciudadDescripcion": partner.city or "",
                }
            )

        # Agregar contacto
        if partner.phone or partner.mobile:
            customer_data["telefono"] = partner.phone or ""
            customer_data["celular"] = partner.mobile or ""

        if partner.email:
            customer_data["email"] = partner.email

        # No-contribuyente: incluir documento de identidad (D024/D025)
        if nat_rec == "2":
            if partner.l10n_py_doc_type:
                customer_data["documentoTipo"] = int(partner.l10n_py_doc_type)
            if partner.l10n_py_doc_number:
                customer_data["documentoNumero"] = partner.l10n_py_doc_number

        return customer_data

    def _prepare_payment_condition(self):
        """Prepare payment condition"""
        payment_condition = {
            "tipo": (2 if self.invoice_payment_term_id else 1),  # 1: Cash, 2: Credit
        }

        if self.invoice_payment_term_id:
            # It is credit
            payment_condition["credito"] = {
                "tipo": 1,  # 1: Plazo, 2: Cuotas
                "plazo": (
                    f"{self.invoice_payment_term_id.line_ids[0].days} days"
                    if self.invoice_payment_term_id.line_ids
                    else "0 days"
                ),
                "cuotas": len(self.invoice_payment_term_id.line_ids),
            }

            # Prepare installment information
            cuotas = []
            sign = self.direction_sign
            payment_terms = self.invoice_payment_term_id._compute_terms(
                date_ref=self.invoice_date or fields.Date.today(),
                currency=self.currency_id,
                company=self.company_id,
                tax_amount=self.amount_tax_signed,
                tax_amount_currency=self.amount_tax * sign,
                sign=sign,
                untaxed_amount=self.amount_untaxed_signed,
                untaxed_amount_currency=self.amount_untaxed * sign,
            )
            for term_line in payment_terms.get("line_ids", []):
                date_due = term_line.get("date")
                amount = term_line.get("foreign_amount")
                cuotas.append(
                    {
                        "moneda": self.currency_id.name,
                        "monto": amount,
                        "vencimiento": (
                            date_due.strftime("%Y-%m-%d")
                            if hasattr(date_due, "strftime")
                            else str(date_due)
                        ),
                    }
                )

            payment_condition["credito"]["infoCuotas"] = cuotas
        else:
            # Es contado
            payment_condition["entregas"] = [
                {
                    "tipo": int(self.l10n_py_payment_type or "1"),
                    "monto": str(self.amount_total),
                    "moneda": self.currency_id.name,
                    "cambio": 0,
                }
            ]

        return payment_condition

    def _prepare_invoice_lines(self):
        """Prepare invoice lines"""
        items = []

        for line in self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
        ):
            # Determinar tasa de VAT
            iva_rate = 10  # Por defecto 10%
            iva_type = 1  # Gravado VAT

            for tax in line.tax_ids:
                if tax.amount == 5:
                    iva_rate = 5
                elif tax.amount == 0:
                    iva_type = 3  # Exenta
                    iva_rate = 0

            # Calcular base gravable e liquidação VAT por linha (SIFEN)
            base_gravada = 0.0
            liquidacion_iva = 0.0
            if iva_rate > 0 and line.price_total:
                base_gravada = line.price_total / (1 + iva_rate / 100)
                liquidacion_iva = line.price_total - base_gravada

            item = {
                "codigo": (
                    line.product_id.default_code or f"PROD-{line.product_id.id}"
                ),
                "descripcion": line.name or line.product_id.name,
                "observacion": "",
                "ncm": (
                    line.product_id.l10n_py_ncm_code
                    if hasattr(line.product_id, "l10n_py_ncm_code")
                    else ""
                )
                or "",
                "unidadMedida": 77,  # UNI - Unidad
                "cantidad": line.quantity,
                "precioUnitario": line.price_unit,
                "cambio": 0,
                "ivaTipo": iva_type,
                "ivaBase": 100,
                "iva": iva_rate,
                "baseGravada": round(base_gravada, 2),
                "liquidacionIva": round(liquidacion_iva, 2),
                "lote": "",
                "vencimiento": "",
            }

            items.append(item)

        return items

    def _prepare_transport_data(self):
        """Preparar datos de transporte (Grupo G SIFEN)."""
        t = self.l10n_py_transport_id
        data = {
            "modalidad": int(t.transport_mode),
        }
        if t.transport_type:
            data["tipo"] = int(t.transport_type)
        if t.freight_responsibility:
            data["responsableFlete"] = int(t.freight_responsibility)
        if t.incoterm:
            data["condicionNegociacion"] = t.incoterm
        if t.manifest_number:
            data["numeroManifest"] = t.manifest_number
        if t.transport_start_date:
            data["fechaInicio"] = t.transport_start_date.strftime("%Y-%m-%d")
        if t.transport_end_date:
            data["fechaFin"] = t.transport_end_date.strftime("%Y-%m-%d")

        # Departure point
        if t.departure_address:
            data["salida"] = {
                "direccion": t.departure_address,
                "numeroCasa": t.departure_house or 0,
                "departamento": t.departure_department or 0,
                "distrito": t.departure_district or 0,
                "ciudad": t.departure_city or 0,
            }

        # Transportr
        if t.transporter_name:
            data["transportista"] = {
                "naturaleza": t.transporter_nature or "1",
                "nombre": t.transporter_name,
                "ruc": t.transporter_ruc or "",
                "dv": t.transporter_dv or "",
                "choferDocument": t.driver_doc_number or "",
                "choferName": t.driver_name or "",
            }

        # Vehicles
        if t.vehicle_ids:
            data["vehiculos"] = [
                {
                    "tipo": v.vehicle_type,
                    "marca": v.brand,
                    "numero": v.plate_number,
                }
                for v in t.vehicle_ids
            ]

        # Deliveries
        if t.delivery_ids:
            data["entregas"] = [
                {
                    "direccion": d.address,
                    "numeroCasa": d.house_number or 0,
                    "departamento": d.department,
                    "distrito": d.district or 0,
                    "ciudad": d.city,
                }
                for d in t.delivery_ids
            ]

        return data

    def _prepare_autofactura_data(self):
        """Prepare Electronic Self-Invoice data (Group E — gCamAE)."""
        return {
            "tipoConstancia": int(self.l10n_py_afe_constancia_type or "1"),
            "numeroConstancia": self.l10n_py_afe_constancia_number or "",
            "numeroControl": self.l10n_py_afe_constancia_control or "",
            "tipoDocumentoVendedor": int(self.l10n_py_afe_vendor_doc_type or "1"),
            "numeroDocumentoVendedor": self.l10n_py_afe_vendor_doc_number or "",
            "nombreVendedor": self.l10n_py_afe_vendor_name or "",
            "direccionVendedor": self.l10n_py_afe_vendor_address or "",
            "numeroCasaVendedor": self.l10n_py_afe_vendor_house or 0,
            "departamentoVendedor": self.l10n_py_afe_vendor_department or 0,
            "distritoVendedor": self.l10n_py_afe_vendor_district or 0,
            "ciudadVendedor": self.l10n_py_afe_vendor_city or 0,
            "direccionProvision": self.l10n_py_afe_provision_address or "",
            "departamentoProvision": self.l10n_py_afe_provision_department or 0,
            "distritoProvision": self.l10n_py_afe_provision_district or 0,
            "ciudadProvision": self.l10n_py_afe_provision_city or 0,
        }

    def _get_edi_sequence_number(self):
        """Obtener number de sequence para EDI"""
        if self.l10n_py_invoice_number:
            return str(self.l10n_py_invoice_number).zfill(7)
        if self.name:
            number = "".join(filter(str.isdigit, self.name.split("/")[-1]))
            return number.zfill(7)[-7:]
        return "0000001"

    def _validate_afe_data(self, docs):
        """Validate Electronic Self-Invoice specific data (code 4)."""
        errors = []
        if len(docs) != 1:
            errors.append(
                self.env._("Self-invoice: must have exactly 1 associated document.")
            )
        elif docs[0].association_type != "3":
            errors.append(
                self.env._(
                    "Self-invoice: the associated document must "
                    "be an electronic certificate (constancia)."
                )
            )
        required_fields = [
            ("l10n_py_afe_constancia_type", "the constancia type"),
            ("l10n_py_afe_constancia_number", "the constancia number"),
            ("l10n_py_afe_constancia_control", "the control number"),
            ("l10n_py_afe_vendor_doc_number", "the vendor document number"),
            ("l10n_py_afe_vendor_name", "the vendor name"),
            ("l10n_py_afe_vendor_address", "the vendor address"),
        ]
        for field_name, desc in required_fields:
            if not getattr(self, field_name):
                errors.append(
                    self.env._("Self-invoice: %(desc)s is required.", desc=desc)
                )
        return errors

    def _validate_edi_document_type(self):
        """Validate specific requirements by DTE type.

        Called before EDI send. Returns list of errors.
        """
        errors = []
        code = (
            self.l10n_latam_document_type_id.code
            if self.l10n_latam_document_type_id
            else ""
        )
        docs = self.l10n_py_associated_document_ids

        # AFE (code=4): exactly 1 certificate + seller data
        if code == "4":
            errors.extend(self._validate_afe_data(docs))

        # NCE (code=5): exactly 1 associated document
        elif code == "5":
            if len(docs) != 1:
                errors.append(
                    self.env._(
                        "Electronic Credit Note: must have "
                        "exactly 1 associated document."
                    )
                )

        # NDE (code=6): exactly 1 associated document
        elif code == "6":
            if len(docs) != 1:
                errors.append(
                    self.env._(
                        "Electronic Debit Note: must have "
                        "exactly 1 associated document."
                    )
                )

        # NRE (code=7): validations NRE
        elif code == "7":
            if not self.l10n_py_nre_motive:
                errors.append(
                    self.env._("Remission Note: motivo (reason) is required.")
                )
            # Reason "1" (sale transfer) without doc → requires estimated date
            if self.l10n_py_nre_motive == "1" and not docs:
                if not self.l10n_py_nre_estimated_invoice_date:
                    errors.append(
                        self.env._(
                            "NRE sale transfer without associated "
                            "document: estimated invoicing date is required."
                        )
                    )
            # Estimated date cannot exceed the month after emission
            if self.l10n_py_nre_estimated_invoice_date and self.invoice_date:
                est_date = self.l10n_py_nre_estimated_invoice_date
                inv_date = self.invoice_date
                max_allowed = inv_date + relativedelta(months=1, day=31)
                if est_date > max_allowed:
                    errors.append(
                        self.env._(
                            "The estimated invoicing date cannot "
                            "exceed the month after emission."
                        )
                    )
            # Reason "5" (local-to-local transfer) → recipient RUC = issuer RUC
            if self.l10n_py_nre_motive == "5":
                partner_ruc = self.partner_id.l10n_py_ruc or ""
                company_ruc = self.company_id.partner_id.l10n_py_ruc or ""
                if partner_ruc != company_ruc:
                    errors.append(
                        self.env._(
                            "Transfer between locations: the receiver's "
                            "RUC must match the issuer's."
                        )
                    )

        return errors

    def _validate_edi_data(self):
        """Validate datos antes de enviar a EDI"""
        errors = []

        # Validate datos de la empresa
        company = self.company_id
        if not company.l10n_py_ruc:
            errors.append(self.env._("Configure the company RUC"))

        # Validate datos del cliente (F15)
        partner = self.partner_id
        if partner.l10n_py_taxpayer_type == "1" and not partner.l10n_py_ruc:
            errors.append(self.env._("Taxpayer customer must have a RUC"))
        if partner.l10n_py_taxpayer_type == "2" and not partner.l10n_py_doc_number:
            errors.append(
                self.env._(
                    "Non-taxpayer customer must have an identity document number"
                )
            )

        if not partner.street:
            errors.append(self.env._("Customer address is required"))

        # Validate datos del diario
        journal = self.journal_id
        if not journal.l10n_py_authorization_id:
            errors.append(
                self.env._("Configure the authorization (timbrado) in the journal")
            )

        if (
            journal.l10n_py_authorization_validity
            and journal.l10n_py_authorization_validity < fields.Date.today()
        ):
            errors.append(self.env._("The authorization has expired"))

        # Validate productos
        for line in self.invoice_line_ids.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
        ):
            if hasattr(line.product_id, "l10n_py_ncm_code"):
                if not line.product_id.l10n_py_ncm_code:
                    errors.append(
                        self.env._(
                            "Product %(name)s does not have an NCM code",
                            name=line.product_id.name,
                        )
                    )

        # Validate requisitos por tipo de documento (F03-F07)
        errors.extend(self._validate_edi_document_type())

        # Validate mandatory denomination (> Gs. 7,000,000)
        _NOMINACION_THRESHOLD = 7000000
        if self.currency_id.name == "PYG" and self.amount_total > _NOMINACION_THRESHOLD:
            if partner.l10n_py_taxpayer_type == "2" and not partner.l10n_py_doc_number:
                errors.append(
                    self.env._(
                        "Invoices over Gs. 7,000,000 cannot be issued "
                        "without identifying the recipient."
                    )
                )

        if errors:
            raise UserError("\n".join(errors))

        return True

    def _log_edi_operation(
        self,
        operation_type,
        provider,
        response_data=None,
        success=True,
        error_message=None,
        duration_ms=0,
    ):
        """Log an EDI operation to l10n_py_edi_log.

        Args:
            operation_type: send | status | cancel | event | validate
            provider: sifen | factpy | facturasend | local
            response_data: dict response from connector
            success: whether the operation succeeded
            error_message: error string if failed
            duration_ms: execution time in milliseconds
        """
        try:
            self.env["l10n_py.edi.log"].log_operation(
                operation_type=operation_type,
                provider=provider,
                document=self,
                response_data=response_data,
                success=success,
                error_message=error_message,
                execution_time=duration_ms,
            )
        except Exception as e:
            _logger.warning("Failed to log EDI operation: %s", str(e))

    # ============== PUBLIC METHODS ==============

    def _get_edi_connector(self):
        """Search the company's EDI connector."""
        connector = (
            self.env["l10n_py.edi.connector"]
            .sudo()
            .search([("company_id", "=", self.company_id.id)], limit=1)
        )
        if not connector:
            raise UserError(self.env._("No EDI connector configured for this company"))
        return connector

    def _target_new_tab(self, attachment_id):
        """Open an ir.attachment inline in a new browser tab."""
        if attachment_id:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment_id.id}/{attachment_id.name}",
                "target": "new",
            }

    def action_preview_xml(self):
        """Generate y mostrar XML sin firmar ni enviar (preview)."""
        self.ensure_one()
        self._validate_edi_data()
        document_data = self._prepare_edi_document_data()
        connector = self._get_edi_connector()
        xml_string = connector.preview_document(document_data)
        xml_b64 = b64.b64encode(xml_string.encode("utf-8"))

        attachment = self.env["ir.attachment"].create(
            {
                "name": f"preview_{self.name or self.id}.xml",
                "datas": xml_b64,
                "mimetype": "text/xml",
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return self._target_new_tab(attachment)

    def action_preview_kude(self):
        """Generate KuDE (PDF) a partir del XML preview via pykude."""
        self.ensure_one()
        self._validate_edi_data()
        document_data = self._prepare_edi_document_data()
        connector = self._get_edi_connector()
        xml_string = connector.preview_document(document_data)

        try:
            from pykude import auto_kude
            from pykude.kude_fe.config import KudeFeConfig
        except ImportError as err:
            raise UserError(
                self.env._("pykude is not available in this environment")
            ) from err

        xml_content = xml_string

        config = KudeFeConfig()
        if self.company_id.logo:
            config.logo = b64.b64decode(self.company_id.logo)

        kude = auto_kude(xml=xml_content, config=config)
        pdf_bytes = kude.output()

        attachment = self.env["ir.attachment"].create(
            {
                "name": f"KUDE_preview_{self.name or self.id}.pdf",
                "datas": b64.b64encode(pdf_bytes),
                "mimetype": "application/pdf",
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return self._target_new_tab(attachment)

    def action_send_edi(self):
        """Send documento a sistema EDI"""
        self.ensure_one()

        # Validate datos
        self._validate_edi_data()

        # Preparar datos
        document_data = self._prepare_edi_document_data()

        # Obtener conector configurado
        connector = self._get_edi_connector()
        provider = connector.provider_type or "sifen"

        try:
            # Send documento
            self.l10n_py_edi_status = "sent"

            t0 = time.time()
            response = connector.send_document(document_data)
            duration_ms = (time.time() - t0) * 1000

            # Log operation
            self._log_edi_operation(
                "send",
                provider,
                response_data=response,
                success=response.get("success", False),
                error_message=response.get("error"),
                duration_ms=duration_ms,
            )

            # Procesar respuesta
            if response.get("success"):
                self._process_edi_response(response)
            else:
                self.l10n_py_edi_status = "rejected"
                self.l10n_py_edi_rejected_date = fields.Datetime.now()
                self.l10n_py_edi_message = response.get("error", "Unknown error")

        except Exception as e:
            _logger.error("Error sending EDI: %s", str(e))
            self.l10n_py_edi_status = "error"
            self.l10n_py_edi_message = str(e)
            raise UserError(
                self.env._("Error sending document: %(value)s", value=str(e))
            ) from e

    def _process_edi_response(self, response):
        """Procesar respuesta exitosa del EDI"""
        self.ensure_one()

        result = response.get("result", {})

        # Save CDC y otros datos
        if result.get("deList"):
            de_data = result["deList"][0]
            vals = {
                "l10n_py_cdc": de_data.get("cdc"),
                "l10n_py_qr_string": de_data.get("qr"),
                "l10n_py_edi_status": "accepted",
                "l10n_py_edi_batch_id": result.get("loteId"),
                "l10n_py_edi_message": self.env._("Document accepted successfully"),
            }
            if not self.l10n_py_edi_accepted_date:
                vals["l10n_py_edi_accepted_date"] = fields.Datetime.now()
            self.write(vals)

            # Save XML si viene
            if de_data.get("xml"):
                self.l10n_py_edi_xml = b64.b64encode(de_data["xml"].encode("utf-8"))
                self.l10n_py_edi_xml_filename = f"{self.l10n_py_cdc}.xml"

            # Generate QR code binary from qr_string (CDC + signature)
            if de_data.get("qr"):
                try:
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(de_data["qr"])
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    self.l10n_py_qr_code = b64.b64encode(buffer.getvalue())
                except Exception as e:
                    _logger.warning("Error generating QR code: %s", str(e))

            # Auto-generate KuDE al aceptar
            try:
                self._generate_kude()
            except Exception as e:
                _logger.warning("Error generating KuDE: %s", str(e))

    def _validate_cancel_deadline(self):
        """Validate cancellation deadline per SIFEN document type.

        FE/AFE: 48 hours, NCE/NDE/NRE: 168 hours (7 days).
        """
        if not self.invoice_date:
            return
        code = (
            self.l10n_latam_document_type_id.code
            if self.l10n_latam_document_type_id
            else ""
        )
        # FE(1) y AFE(4): 48h, NCE(5)/NDE(6)/NRE(7): 168h
        if code in ("1", "4"):
            max_hours = 48
        else:
            max_hours = 168

        accepted_dt = self.l10n_py_edi_accepted_date or (
            fields.Datetime.from_string(str(self.invoice_date) + " 00:00:00")
            if self.invoice_date
            else None
        )
        if not accepted_dt:
            return
        deadline = accepted_dt + relativedelta(hours=max_hours)
        now = fields.Datetime.now()
        if now > deadline:
            raise UserError(
                self.env._(
                    "The cancellation deadline has expired. "
                    "Limit: %(deadline)s (%(hours)s hours from emission).",
                    deadline=deadline,
                    hours=max_hours,
                )
            )

    def action_cancel_edi(self, motive=None):
        """Cancel electronic document"""
        self.ensure_one()

        if not self.l10n_py_cdc:
            raise UserError(self.env._("Cannot cancel a document without a CDC"))

        self._validate_cancel_deadline()

        connector = self._get_edi_connector()
        provider = connector.provider_type or "sifen"

        t0 = time.time()
        response = connector.cancel_document(self.l10n_py_cdc, reason=motive or "")
        duration_ms = (time.time() - t0) * 1000

        # Log operation
        self._log_edi_operation(
            "cancel",
            provider,
            response_data=response,
            success=response.get("success", False),
            error_message=response.get("error"),
            duration_ms=duration_ms,
        )

        if response.get("success"):
            self.l10n_py_edi_status = "cancelled"
            self.l10n_py_edi_message = self.env._(
                "Cancelled on %(date)s", date=fields.Datetime.now()
            )
            # The CDC uniquely identifies one electronic-document instance in
            # SIFEN. Clear it (and its derived fields) so that any future
            # resend on this record regenerates a fresh CDC instead of
            # reusing a cancelled one, which SIFEN would reject as duplicate.
            self.l10n_py_cdc = False
            self.l10n_py_cdc_emission_date = False
            self.l10n_py_qr_string = False
            self.l10n_py_edi_accepted_date = False
        else:
            raise UserError(
                self.env._(
                    "Error cancelling document: %(error)s",
                    error=response.get("error"),
                )
            )

    def action_retry_edi(self):
        """Retry document sending"""
        self.ensure_one()

        if self.l10n_py_edi_status not in ["error", "rejected"]:
            raise UserError(
                self.env._("Only documents in error or rejected state can be retried")
            )

        return self.action_send_edi()

    def action_download_xml(self):
        """Download the document's XML."""
        self.ensure_one()

        if not self.l10n_py_edi_xml:
            raise UserError(self.env._("No XML available for this document"))

        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/{self._name}/{self.id}/l10n_py_edi_xml/"
                f"{self.l10n_py_edi_xml_filename}?download=true"
            ),
            "target": "self",
        }

    def action_download_kude(self):
        """Download the KUDE (PDF)"""
        self.ensure_one()

        if not self.l10n_py_kude_pdf:
            # Try to generate the KUDE; a failure falls through to a clean message
            try:
                self._generate_kude()
            except Exception as e:
                _logger.warning("Error generating KuDE: %s", str(e))

        if not self.l10n_py_kude_pdf:
            raise UserError(self.env._("No KUDE available for this document"))

        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/{self._name}/{self.id}/l10n_py_kude_pdf/"
                f"{self.l10n_py_kude_filename}?download=true"
            ),
            "target": "self",
        }

    def _generate_kude(self):
        """Generate KUDE (graphical representation of DTE) via pykude."""
        self.ensure_one()
        if not self.l10n_py_edi_xml:
            return
        if not self.l10n_py_cdc:
            raise UserError(
                self.env._(
                    "Cannot generate KUDE without a CDC. "
                    "Please resend the document first."
                )
            )
        try:
            from pykude import auto_kude
            from pykude.kude_fe.config import KudeFeConfig
        except ImportError:
            _logger.warning("pykude not available, skipping KuDE generation")
            return

        xml_content = b64.b64decode(self.l10n_py_edi_xml).decode("utf-8")

        config = KudeFeConfig()
        if self.company_id.logo:
            config.logo = b64.b64decode(self.company_id.logo)

        kude = auto_kude(xml=xml_content, config=config)
        pdf_bytes = kude.output()

        self.l10n_py_kude_pdf = b64.b64encode(pdf_bytes)
        self.l10n_py_kude_filename = f"KUDE_{self.l10n_py_cdc}.pdf"

    # ============== CRON METHODS ==============

    # Minimum minutes between status checks for a document
    _EDI_STATUS_CHECK_COOLDOWN_MIN = 10

    @api.model
    def _cron_check_edi_status(self):
        """Verify status of sent documents and process contingency queue.

        Prioritizes documents close to the 72h deadline.
        Uses cooldown to avoid checking the same document too frequently.
        """
        # 1. Process contingency queue (to_send pending with contingency type)
        contingency_docs = self.search(
            [
                ("l10n_py_edi_status", "=", "to_send"),
                ("l10n_py_emission_type", "=", "2"),
            ],
            order="l10n_py_transmission_deadline asc",
        )
        for doc in contingency_docs:
            try:
                doc.action_send_edi()
            except Exception:
                _logger.warning("Error retrying contingency doc %s", doc.name)

        # 2. Verify status of already-sent documents with cooldown
        pending_docs = self.search(
            [
                ("l10n_py_edi_status", "in", ["sent", "processing"]),
                ("l10n_py_edi_batch_id", "!=", False),
            ],
            order="write_date asc",  # Oldest first — prioritize stale documents
        )

        now = fields.Datetime.now()
        cooldown_delta = self._EDI_STATUS_CHECK_COOLDOWN_MIN * 60

        for doc in pending_docs:
            # Cooldown: skip if document was updated recently
            # Use write_date as proxy for last check time
            last_update = doc.write_date
            if last_update:
                seconds_since_update = (now - last_update).total_seconds()
                if seconds_since_update < cooldown_delta:
                    # Still in cooldown window — skip this document
                    continue

            try:
                connector = (
                    self.env["l10n_py.edi.connector"]
                    .sudo()
                    .search([("company_id", "=", doc.company_id.id)], limit=1)
                )
                if not connector:
                    continue
                response = connector.check_status(doc.l10n_py_edi_batch_id)
                if response.get("success"):
                    doc._process_edi_response(response)
            except Exception as e:
                _logger.error(
                    "Error checking EDI status for %s: %s",
                    doc.name,
                    str(e),
                )
