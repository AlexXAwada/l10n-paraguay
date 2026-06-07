from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_py")
class TestEdiDemoScenarios(TransactionCase):
    """Tests of EDI scenarios using demo data.

    Valida que os dados demo foram carregados corretamente e que
    as validações por tipo de documento funcionam com dados reais.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.company = cls.env.ref("base.main_company")
        cls.country_py = cls.env.ref("base.py")
        cls.company.write(
            {
                "country_id": cls.country_py.id,
                "account_fiscal_country_id": cls.country_py.id,
            }
        )
        # Set the RUC on the company partner (via vat field)
        ruc_type = cls.env.ref("l10n_py_base.it_ruc", raise_if_not_found=False)
        cls.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
            }
        )

        # Document types (from data/, always available)
        cls.doc_type_fe = cls.env.ref("l10n_py_account.dc_py_f")
        cls.doc_type_af = cls.env.ref("l10n_py_account.dc_py_af")
        cls.doc_type_nc = cls.env.ref("l10n_py_account.dc_py_nc")
        cls.doc_type_nd = cls.env.ref("l10n_py_account.dc_py_nd")
        cls.doc_type_nr = cls.env.ref("l10n_py_account.dc_py_nr")

        # Accounts
        account_receivable = cls.env["account.account"].search(
            [
                ("company_ids", "in", [cls.company.id]),
                ("account_type", "=", "asset_receivable"),
            ],
            limit=1,
        )
        if not account_receivable:
            account_receivable = cls.env["account.account"].create(
                {
                    "name": "Cuentas por Cobrar",
                    "code": "110001",
                    "account_type": "asset_receivable",
                    "reconcile": True,
                    "company_ids": [(6, 0, [cls.company.id])],
                }
            )

        # Partners (created here, not from demo)
        cls.partner_contribuyente = cls.env["res.partner"].create(
            {
                "name": "Taxpayer General Test",
                "country_id": cls.country_py.id,
                "l10n_py_ruc": "80012345",
                "l10n_py_taxpayer_type": "1",
                "property_account_receivable_id": account_receivable.id,
                "property_account_payable_id": account_receivable.id,
            }
        )
        cls.partner_servicios = cls.env["res.partner"].create(
            {
                "name": "Taxpayer Servicios Test",
                "country_id": cls.country_py.id,
                "l10n_py_ruc": "80067890",
                "l10n_py_taxpayer_type": "1",
                "property_account_receivable_id": account_receivable.id,
                "property_account_payable_id": account_receivable.id,
            }
        )
        cls.partner_no_contribuyente = cls.env["res.partner"].create(
            {
                "name": "No Taxpayer Test",
                "country_id": cls.country_py.id,
                "l10n_py_taxpayer_type": "2",
                "property_account_receivable_id": account_receivable.id,
                "property_account_payable_id": account_receivable.id,
            }
        )

        # Products
        cls.product_10 = cls.env["product.product"].create(
            {"name": "Producto VAT 10%", "list_price": 1100000.0}
        )
        cls.product_5 = cls.env["product.product"].create(
            {"name": "Producto VAT 5%", "list_price": 525000.0}
        )

        # Journal
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Ventas DS Test",
                "type": "sale",
                "code": "VDS",
                "company_id": cls.company.id,
                "l10n_latam_use_documents": True,
            }
        )

        # Authorization
        today = date.today()
        cls.authorization = cls.env["account.authorization"].create(
            {
                "name": "11223399",
                "date_from": today - timedelta(days=30),
                "date_to": today + timedelta(days=335),
                "invoice_number_from": 1,
                "invoice_number_to": 10000,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": cls.doc_type_fe.id,
                "company_id": cls.company.id,
            }
        )

        cls.valid_cdc = "0" * 44

    def _create_move(self, doc_type_code, move_type=None, **kwargs):
        """Helper to create move with specific document type."""
        if move_type is None:
            move_type = "out_refund" if doc_type_code == "5" else "out_invoice"

        doc_type = {
            "1": self.doc_type_fe,
            "4": self.doc_type_af,
            "5": self.doc_type_nc,
            "6": self.doc_type_nd,
            "7": self.doc_type_nr,
        }[doc_type_code]

        vals = {
            "move_type": move_type,
            "partner_id": kwargs.pop("partner_id", self.partner_contribuyente.id),
            "journal_id": self.journal.id,
            "l10n_latam_document_type_id": doc_type.id,
        }
        vals.update(kwargs)
        return self.env["account.move"].create(vals)

    # ============== NCE: Electronic Credit Note ==============

    def test_nce_requires_one_associated_document(self):
        """NCE without associated document → validation error"""
        move = self._create_move("5")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("exactamente 1", errors[0])

    def test_nce_with_electronic_association_valid(self):
        """NCE with associated CDC → validation OK"""
        move = self._create_move("5")
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "1",
                "cdc": self.valid_cdc,
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nce_with_printed_association_valid(self):
        """NCE with associated printed document → validation OK"""
        move = self._create_move("5")
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "2",
                "timbrado": "12345678",
                "establishment": "001",
                "expedition_point": "001",
                "doc_number": "0000001",
                "doc_type_code": "1",
                "doc_date": date.today(),
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nce_multiple_associations_rejected(self):
        """NCE with more than 1 associated document → error"""
        move = self._create_move("5")
        for _i in range(2):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "1",
                    "cdc": self.valid_cdc,
                }
            )
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)

    # ============== NDE: Electronic Debit Note ==============

    def test_nde_requires_one_associated_document(self):
        """NDE without associated document → validation error"""
        move = self._create_move("6")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)

    def test_nde_with_electronic_association_valid(self):
        """NDE with associated CDC → validation OK"""
        move = self._create_move("6")
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "1",
                "cdc": self.valid_cdc,
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    # ============== AFE: Electronic Self-Invoice ==============

    def test_afe_requires_constancia(self):
        """AFE without certificate → validation error"""
        move = self._create_move("4")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("exactamente 1", errors[0])

    def test_afe_with_constancia_no_contribuyente_valid(self):
        """AFE con constancia de no contribuyente + datos vendedor → OK"""
        move = self._create_move(
            "4",
            l10n_py_afe_constancia_type="1",
            l10n_py_afe_constancia_number="00012345678",
            l10n_py_afe_constancia_control="12345678",
            l10n_py_afe_vendor_doc_type="1",
            l10n_py_afe_vendor_doc_number="1234567",
            l10n_py_afe_vendor_name="Juan Perez",
            l10n_py_afe_vendor_address="Calle 1",
        )
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "3",
                "constancia_type": "1",
                "constancia_number": "CONST-NC-TEST-001",
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_afe_with_constancia_microproductor_valid(self):
        """AFE con constancia de microproductor + datos vendedor → OK"""
        move = self._create_move(
            "4",
            l10n_py_afe_constancia_type="2",
            l10n_py_afe_constancia_number="00012345678",
            l10n_py_afe_constancia_control="12345678",
            l10n_py_afe_vendor_doc_type="1",
            l10n_py_afe_vendor_doc_number="9876543",
            l10n_py_afe_vendor_name="Maria Garcia",
            l10n_py_afe_vendor_address="Avda Principal",
        )
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "3",
                "constancia_type": "2",
                "constancia_number": "CONST-MP-TEST-001",
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_afe_wrong_association_type_rejected(self):
        """AFE with electronic doc (instead of certificate) → error"""
        move = self._create_move("4")
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "1",
                "cdc": self.valid_cdc,
            }
        )
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("constancia", errors[0])

    # ============== NRE: Electronic Remission Note ==============

    def test_nre_requires_motive(self):
        """NRE without reason → validation error"""
        move = self._create_move("7")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("motivo", errors[0])

    def test_nre_traslado_venta_with_associated_doc(self):
        """NRE transfer for sale with associated FE → validation OK"""
        move = self._create_move("7", l10n_py_nre_motive="1")
        self.env["l10n_py.associated.document"].create(
            {
                "move_id": move.id,
                "association_type": "1",
                "cdc": self.valid_cdc,
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_traslado_venta_without_doc_requires_date(self):
        """NRE traslado por venta sin FE y sin fecha estimada → error"""
        move = self._create_move("7", l10n_py_nre_motive="1")
        errors = move._validate_edi_document_type()
        self.assertTrue(any("fecha estimada" in e for e in errors))

    def test_nre_traslado_venta_without_doc_with_date_valid(self):
        """NRE traslado por venta sin FE pero con fecha estimada → OK"""
        move = self._create_move(
            "7",
            l10n_py_nre_motive="1",
            l10n_py_nre_estimated_invoice_date=date.today() + timedelta(days=10),
            invoice_date=date.today(),
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_entre_locales_same_ruc(self):
        """NRE between locations with same RUC → validation OK"""
        # Set the RUC on the company partner
        ruc_type = self.env.ref("l10n_py_base.it_ruc", raise_if_not_found=False)
        self.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
            }
        )
        partner_same = self.env["res.partner"].create(
            {
                "name": "Sucursal Test",
                "country_id": self.country_py.id,
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
                "l10n_py_taxpayer_type": "1",
                "street": "Calle Sucursal 123",
            }
        )
        move = self._create_move(
            "7",
            partner_id=partner_same.id,
            l10n_py_nre_motive="5",
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_entre_locales_different_ruc_rejected(self):
        """NRE entre locales con RUC diferente → error"""
        move = self._create_move(
            "7",
            partner_id=self.partner_servicios.id,
            l10n_py_nre_motive="5",
        )
        errors = move._validate_edi_document_type()
        self.assertTrue(any("RUC" in e for e in errors))

    def test_nre_consignacion_valid(self):
        """NRE transfer by consignment → validation OK (no doc required)"""
        move = self._create_move("7", l10n_py_nre_motive="2")
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_exportacion_valid(self):
        """NRE transfer for export → validation OK"""
        move = self._create_move("7", l10n_py_nre_motive="3")
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    # ============== Associated Document Constraints ==============

    def test_associated_doc_electronic_requires_cdc(self):
        """Electronic document without CDC → ValidationError"""
        move = self._create_move("5")
        with self.assertRaises(ValidationError):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "1",
                    # Sin CDC
                }
            )

    def test_associated_doc_electronic_invalid_cdc(self):
        """CDC with invalid format → ValidationError"""
        move = self._create_move("5")
        with self.assertRaises(ValidationError):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "1",
                    "cdc": "123",  # Must be 44 digits
                }
            )

    def test_associated_doc_printed_requires_all_fields(self):
        """Document impreso sin campos obligatorios → ValidationError"""
        move = self._create_move("5")
        with self.assertRaises(ValidationError):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "2",
                    "timbrado": "12345678",
                    # Faltan establishment, expedition_point, etc.
                }
            )

    def test_associated_doc_constancia_requires_type_and_number(self):
        """Certificate without type or number → ValidationError"""
        move = self._create_move("4")
        with self.assertRaises(ValidationError):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "3",
                    "constancia_type": "1",
                    # Sin constancia_number
                }
            )

    # ============== Number Inutilization ==============

    def test_inutilization_valid_range(self):
        """Inutilization with valid range → OK"""
        today = date.today()
        auth = self.env["account.authorization"].create(
            {
                "name": "99001122",
                "date_from": today - timedelta(days=10),
                "date_to": today + timedelta(days=355),
                "invoice_number_from": 1,
                "invoice_number_to": 10000,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": self.doc_type_fe.id,
                "company_id": self.company.id,
            }
        )
        inut = self.env["l10n_py.number.inutilization"].create(
            {
                "authorization_id": auth.id,
                "number_from": 9990,
                "number_to": 10000,
                "motive": "Numbers reservados para pruebas",
            }
        )
        self.assertEqual(inut.quantity, 11)
        self.assertEqual(inut.state, "draft")

    def test_inutilization_exceeds_max_range(self):
        """Inutilization con rango > 1000 → ValidationError"""
        today = date.today()
        auth = self.env["account.authorization"].create(
            {
                "name": "99001133",
                "date_from": today - timedelta(days=10),
                "date_to": today + timedelta(days=355),
                "invoice_number_from": 1,
                "invoice_number_to": 10000,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": self.doc_type_fe.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["l10n_py.number.inutilization"].create(
                {
                    "authorization_id": auth.id,
                    "number_from": 1,
                    "number_to": 5000,
                    "motive": "Range exceeds limit",
                }
            )

    def test_inutilization_outside_authorization(self):
        """Inutilization fuera del rango del timbrado → ValidationError"""
        today = date.today()
        auth = self.env["account.authorization"].create(
            {
                "name": "99001144",
                "date_from": today - timedelta(days=10),
                "date_to": today + timedelta(days=355),
                "invoice_number_from": 1,
                "invoice_number_to": 100,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": self.doc_type_fe.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["l10n_py.number.inutilization"].create(
                {
                    "authorization_id": auth.id,
                    "number_from": 90,
                    "number_to": 150,
                    "motive": "Fuera del rango",
                }
            )

    def test_inutilization_negative_numbers(self):
        """Inutilization with negative numbers → ValidationError"""
        today = date.today()
        auth = self.env["account.authorization"].create(
            {
                "name": "99001155",
                "date_from": today - timedelta(days=10),
                "date_to": today + timedelta(days=355),
                "invoice_number_from": 1,
                "invoice_number_to": 10000,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": self.doc_type_fe.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["l10n_py.number.inutilization"].create(
                {
                    "authorization_id": auth.id,
                    "number_from": -1,
                    "number_to": 10,
                    "motive": "Numbers negativos",
                }
            )
