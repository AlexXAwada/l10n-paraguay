# l10n_py_edi_base/services/cdc_generator.py

"""
CDC (Control Code) Generator for Paraguayan electronic documents
Implementation per SIFEN v150 Technical Manual
"""

import logging
import secrets
from datetime import datetime

_logger = logging.getLogger(__name__)


class CDCGenerator:
    """
    CDC (Control Code) Generator for electronic documents

    CDC Format (44 digits):
    - Issuer RUC (8 digits)
    - Document type (2 digits)
    - Establishment (3 digits)
    - Expedition point (3 digits)
    - Number del documento (7 digits)
    - Code de security (9 digits)
    - Date/time of emission (11 digits)
    - Check digit (1 digit)
    """

    # Multiplicadores para digit check digit (posiciones 1-42)
    MULTIPLIERS = [2, 3, 4, 5, 6, 7, 8, 9] * 6  # Repetir hasta 42 posiciones

    @classmethod
    def generate(
        cls,
        company_ruc,
        doc_type,
        establishment,
        expedition_point,
        sequence,
        emission_date=None,
        security_code=None,
    ):
        """
        Generate CDC per SIFEN v150 specification

        Args:
            company_ruc (str): Company RUC issuera (sin DV)
            doc_type (int): Tipo de documento (1=FE, 4=Autofactura, etc.)
            establishment (str): Establishment (3 digits)
            expedition_point (str): Expedition point (3 digits)
            sequence (int): Number sequential del documento
            emission_date (datetime): Emission date (optional)
            security_code (str|int): Code de security a usar (opcional, 8-9 digits)

        Returns:
            str: CDC completo con digit check digit (44 digits)
        """
        if emission_date is None:
            emission_date = datetime.now()

        # Validate parameters
        cls._validate_parameters(
            company_ruc, doc_type, establishment, expedition_point, sequence
        )

        # Construir CDC base (43 digits)
        cdc_base = cls._build_cdc_base(
            company_ruc,
            doc_type,
            establishment,
            expedition_point,
            sequence,
            emission_date,
            security_code=security_code,
        )

        # Calcular digit check digit
        check_digit = cls._calculate_check_digit(cdc_base)

        # CDC final (44 digits)
        cdc_complete = cdc_base + str(check_digit)

        # Validate formato final
        if len(cdc_complete) != 44:
            raise ValueError(f"CDC debe tener 44 digits, generado: {len(cdc_complete)}")

        _logger.info("CDC generado: %s", cdc_complete)
        return cdc_complete

    @classmethod
    def _validate_parameters(
        cls, company_ruc, doc_type, establishment, expedition_point, sequence
    ):
        """Validate input parameters"""
        # Validate RUC
        ruc_clean = "".join(filter(str.isdigit, str(company_ruc)))
        if len(ruc_clean) < 6 or len(ruc_clean) > 8:
            raise ValueError(f"Invalid RUC: {company_ruc}")

        # Validate tipo de documento
        if not isinstance(doc_type, int) or doc_type < 1 or doc_type > 99:
            raise ValueError(f"Invalid document type: {doc_type}")

        # Validate establishment
        est_clean = str(establishment).zfill(3)
        if len(est_clean) != 3 or not est_clean.isdigit():
            raise ValueError(f"Invalid establishment: {establishment}")

        # Validate expedition point
        exp_clean = str(expedition_point).zfill(3)
        if len(exp_clean) != 3 or not exp_clean.isdigit():
            raise ValueError(f"Invalid expedition point: {expedition_point}")

        # Validate sequence
        if not isinstance(sequence, int) or sequence < 1 or sequence > 9999999:
            raise ValueError(f"Invalid sequence: {sequence}")

    @classmethod
    def _build_cdc_base(
        cls,
        company_ruc,
        doc_type,
        establishment,
        expedition_point,
        sequence,
        emission_date,
        security_code=None,
    ):
        """
        Construir base del CDC (43 digits)

        Formato conforme SIFEN:
        - RUC: 8 digits
        - Tipo documento: 2 digits
        - Establishment: 3 digits
        - Punto expedition: 3 digits
        - Number documento: 7 digits
        - Code security: 9 digits
        - Date/hora: 11 digits (YYMMDDHHmm + random)
        """
        # Company RUC (8 digits - extraer solo numbers)
        ruc_clean = "".join(filter(str.isdigit, str(company_ruc)))
        cdc = ruc_clean[:8].zfill(8)

        # Document type (2 digits)
        cdc += str(doc_type).zfill(2)

        # Establishment (3 digits)
        cdc += str(int(establishment)).zfill(3)

        # Expedition point (3 digits)
        cdc += str(int(expedition_point)).zfill(3)

        # Number del documento (7 digits)
        cdc += str(sequence).zfill(7)

        # Code de security (9 digits)
        if security_code is not None:
            sc_9 = str(security_code)[:9].zfill(9)
        else:
            sc_9 = str(cls._generate_security_code()).zfill(9)
        cdc += sc_9

        # Date y hora (11 digits)
        datetime_code = cls._generate_datetime_code(emission_date)
        cdc += datetime_code

        if len(cdc) != 43:
            raise ValueError(f"CDC base debe tener 43 digits, generado: {len(cdc)}")

        return cdc

    @classmethod
    def _generate_security_code(cls):
        """Generate security code random (9 digits)"""
        return secrets.randbelow(900000000) + 100000000

    @classmethod
    def _generate_datetime_code(cls, emission_date):
        """
        Generate code de fecha/hora (11 digits)

        Formato: YYMMDDHHmm + digit random
        """
        date_str = emission_date.strftime("%y%m%d%H%M")  # 10 digits
        random_digit = secrets.randbelow(10)  # 1 digit

        return date_str + str(random_digit)

    @classmethod
    def _calculate_check_digit(cls, cdc_base):
        """
        Calcular digit check digit usando module 11

        Args:
            cdc_base (str): CDC base (43 digits)

        Returns:
            int: Check digit (0-9)
        """
        if len(cdc_base) != 43:
            raise ValueError(
                f"CDC base debe tener 43 digits, recibido: {len(cdc_base)}"
            )

        # Calcular suma ponderada
        total = 0
        for i, digit in enumerate(cdc_base):
            multiplier = cls.MULTIPLIERS[i % len(cls.MULTIPLIERS)]
            total += int(digit) * multiplier

        # Compute remainder of division by 11
        remainder = total % 11

        # Determinar digit check digit
        if remainder < 2:
            return remainder
        else:
            return 11 - remainder

    @classmethod
    def validate_cdc(cls, cdc):
        """
        Validate formato y digit check digit de un CDC

        Args:
            cdc (str): CDC a ser validado

        Returns:
            tuple: (is_valid, error_message)
        """
        if not cdc:
            return False, "CDC es obligatorio"

        # Verify length
        if len(cdc) != 44:
            return False, f"CDC must have 44 digits, received: {len(cdc)}"

        # Verify it contains only digits
        if not cdc.isdigit():
            return False, "CDC must contain only digits"

        # Separar base y digit check digit
        cdc_base = cdc[:43]
        check_digit = int(cdc[43])

        # Calcular digit check digit esperado
        try:
            calculated_digit = cls._calculate_check_digit(cdc_base)
        except Exception as e:
            return False, f"Error calcular DV: {str(e)}"

        if calculated_digit != check_digit:
            return (
                False,
                f"Invalid check digit. "
                f"Expected: {calculated_digit}, "
                f"Received: {check_digit}",
            )

        return True, ""

    @classmethod
    def parse_cdc(cls, cdc):
        """
        Extraer componentes del CDC

        Args:
            cdc (str): CDC completo (44 digits)

        Returns:
            dict: Diccionario con componentes del CDC
        """
        if len(cdc) != 44:
            raise ValueError(f"CDC debe tener 44 digits, recibido: {len(cdc)}")

        return {
            "ruc": cdc[0:8],
            "doc_type": cdc[8:10],
            "establishment": cdc[10:13],
            "expedition_point": cdc[13:16],
            "sequence": cdc[16:23],
            "security_code": cdc[23:32],
            "datetime_code": cdc[32:43],
            "check_digit": cdc[43],
        }

    @classmethod
    def format_cdc(cls, cdc, separator="-"):
        """
        Format CDC for readable display

        Args:
            cdc (str): CDC completo
            separator (str): Separador entre componentes

        Returns:
            str: CDC formateado
        """
        if len(cdc) != 44:
            return cdc

        components = cls.parse_cdc(cdc)

        return (
            f"{components['ruc']}{separator}"
            f"{components['doc_type']}{separator}"
            f"{components['establishment']}{separator}"
            f"{components['expedition_point']}{separator}"
            f"{components['sequence']}{separator}"
            f"{components['security_code']}{separator}"
            f"{components['datetime_code']}{separator}"
            f"{components['check_digit']}"
        )
