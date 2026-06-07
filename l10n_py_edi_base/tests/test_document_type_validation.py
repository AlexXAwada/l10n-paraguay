from datetime import date, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_py")
class TestDocumentTypeValidation(TransactionCase):
    """Tests de validação por tipo de documento (F04-F07)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.country_py = cls.env.ref("base.py")
        cls.company.write(
            {
                "country_id": cls.country_py.id,
                "account_fiscal_country_id": cls.country_py.id,
            }
        )
        ruc_type = cls.env.ref("l10n_py_base.it_ruc", raise_if_not_found=False)
        # Set the RUC on the company partner (via vat field)
        cls.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
            }
        )

        # Document types
        cls.doc_types = {}
        for code, name in [
            ("1", "Electronic Invoice"),
            ("4", "Electronic Self-Invoice"),
            ("5", "Electronic Credit Note"),
            ("6", "Electronic Debit Note"),
            ("7", "Electronic Remission Note"),
        ]:
            dt = cls.env["l10n_latam.document.type"].search(
                [("country_id", "=", cls.country_py.id), ("code", "=", code)],
                limit=1,
            )
            if not dt:
                dt = cls.env["l10n_latam.document.type"].create(
                    {
                        "name": name,
                        "code": code,
                        "country_id": cls.country_py.id,
                        "internal_type": (
                            "credit_note"
                            if code == "5"
                            else "debit_note"
                            if code == "6"
                            else "invoice"
                        ),
                    }
                )
            cls.doc_types[code] = dt

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Test PY",
                "country_id": cls.country_py.id,
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
                "l10n_py_taxpayer_type": "1",
                "street": "Calle Test 123",
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Ventas DT Test",
                "type": "sale",
                "code": "VDT",
                "company_id": cls.company.id,
                "l10n_latam_use_documents": True,
            }
        )

        today = date.today()
        cls.authorization = cls.env["account.authorization"].create(
            {
                "name": "44556688",
                "date_from": today - timedelta(days=30),
                "date_to": today + timedelta(days=335),
                "invoice_number_from": 1,
                "invoice_number_to": 10000,
                "establishment": "001",
                "expedition_point": "001",
                "l10n_latam_document_type_id": cls.doc_types["1"].id,
                "company_id": cls.company.id,
            }
        )

        cls.valid_cdc = "0" * 44

    def _create_move(self, doc_type_code, **kwargs):
        """Helper to create move with specific document type"""
        # NCE (code=5) uses out_refund because its internal_type is credit_note
        move_type = "out_refund" if doc_type_code == "5" else "out_invoice"
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "l10n_latam_document_type_id": self.doc_types[doc_type_code].id,
        }
        vals.update(kwargs)
        return self.env["account.move"].create(vals)

    # ============== F04: AFE (Autofactura) ==============

    def test_afe_with_constancia(self):
        """F04: AFE com constância + dados vendedor → sem erros"""
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
                "constancia_number": "CONST-001",
            }
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_afe_without_constancia(self):
        """F04: AFE sem documento associado → erro"""
        move = self._create_move("4")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("exactly 1", errors[0])

    def test_afe_wrong_association_type(self):
        """F04: AFE with wrong type (electronic instead of certificate) → error"""
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

    def test_afe_multiple_associations(self):
        """F04: AFE with multiple documents → error"""
        move = self._create_move("4")
        for i in range(2):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "3",
                    "constancia_type": "1",
                    "constancia_number": f"CONST-{i}",
                }
            )
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("exactly 1", errors[0])

    # ============== F05: NCE (Credit Note) ==============

    def test_nce_electronic_association(self):
        """F05: NCE with electronic doc → no errors"""
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

    def test_nce_printed_association(self):
        """F05: NCE com doc impresso → sem erros"""
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

    def test_nce_without_association(self):
        """F05: NCE sem documento associado → erro"""
        move = self._create_move("5")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)

    def test_nce_multiple_associations(self):
        """F05: NCE with multiple documents → error"""
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

    # ============== F06: NDE (Debit Note) ==============

    def test_nde_electronic_association(self):
        """F06: NDE with electronic doc → no errors"""
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

    def test_nde_without_association(self):
        """F06: NDE sem documento associado → erro"""
        move = self._create_move("6")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)

    def test_nde_multiple_associations(self):
        """F06: NDE with multiple documents → error"""
        move = self._create_move("6")
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

    # ============== F07: NRE (Electronic Remission Note) ==============

    def test_nre_traslado_venta_with_fe(self):
        """F07: NRE traslado por venta com FE associada → sem erros"""
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

    def test_nre_without_motive(self):
        """F07: NRE sem motivo → erro"""
        move = self._create_move("7")
        errors = move._validate_edi_document_type()
        self.assertTrue(errors)
        self.assertIn("motivo", errors[0])

    def test_nre_without_fe_requires_date(self):
        """F07: NRE traslado venta sem FE e sem data estimada → erro"""
        move = self._create_move("7", l10n_py_nre_motive="1")
        errors = move._validate_edi_document_type()
        self.assertTrue(any("estimated invoicing date" in e for e in errors))

    def test_nre_without_fe_with_date(self):
        """F07: NRE traslado venta sem FE com data estimada → sem erros"""
        move = self._create_move(
            "7",
            l10n_py_nre_motive="1",
            l10n_py_nre_estimated_invoice_date=date.today() + timedelta(days=10),
            invoice_date=date.today(),
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_same_ruc_transfer(self):
        """F07: NRE entre locales com mesmo RUC → sem erros"""
        # Set the RUC directly on the company partner_id
        ruc_type = self.env.ref("l10n_py_base.it_ruc", raise_if_not_found=False)
        self.company.partner_id.write(
            {
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
            }
        )
        # Partner com mesmo RUC da empresa
        partner_same = self.env["res.partner"].create(
            {
                "name": "Sucursal",
                "country_id": self.country_py.id,
                "l10n_latam_identification_type_id": ruc_type.id if ruc_type else False,
                "vat": "80009401-0",
                "l10n_py_taxpayer_type": "1",
                "street": "Calle Sucursal",
            }
        )
        move = self._create_move(
            "7",
            partner_id=partner_same.id,
            l10n_py_nre_motive="5",
        )
        errors = move._validate_edi_document_type()
        self.assertFalse(errors)

    def test_nre_different_ruc_transfer(self):
        """F07: NRE entre locales com RUC diferente → erro"""
        partner_other = self.env["res.partner"].create(
            {
                "name": "Otra Company",
                "country_id": self.country_py.id,
                "l10n_py_ruc": "99999999",
                "l10n_py_taxpayer_type": "1",
                "street": "Calle Otra",
            }
        )
        move = self._create_move(
            "7",
            partner_id=partner_other.id,
            l10n_py_nre_motive="5",
        )
        errors = move._validate_edi_document_type()
        self.assertTrue(any("RUC" in e for e in errors))

    def test_nre_multiple_associations(self):
        """F07: NRE allows multiple associated documents"""
        move = self._create_move("7", l10n_py_nre_motive="1")
        for _i in range(3):
            self.env["l10n_py.associated.document"].create(
                {
                    "move_id": move.id,
                    "association_type": "1",
                    "cdc": self.valid_cdc,
                }
            )
        errors = move._validate_edi_document_type()
        # NRE accepts multiple — no error for quantity
        self.assertFalse(errors)
