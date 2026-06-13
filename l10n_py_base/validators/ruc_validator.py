# l10n_py_base/validators/ruc_validator.py

"""
Robust validator for Paraguayan RUC
Implements full validation according to SET specifications (Module 11)
"""

import logging
import re

_logger = logging.getLogger(__name__)


class RUCValidator:
    """Robust validator for Paraguayan RUC"""

    # Cyclic weights for check digit calculation (Module 11 SET)
    WEIGHTS = [2, 3, 4, 5, 6, 7, 8, 9]

    @classmethod
    def validate(cls, ruc):
        """
        Full validation of Paraguayan RUC

        Args:
            ruc (str): RUC to be validated

        Returns:
            tuple: (is_valid, error_message)
        """
        if not ruc:
            return False, "RUC is required"

        # Clean special characters
        clean_ruc = re.sub(r"[^\d-]", "", ruc)

        # Check basic format (accepts with or without hyphen)
        if not re.match(r"^\d{6,8}(-\d)?$", clean_ruc):
            return False, "Invalid format. Use: XXXXXXX-D or XXXXXXX"

        # Separate RUC and check digit if hyphen present
        if "-" in clean_ruc:
            ruc_number, check_digit = clean_ruc.split("-")
        else:
            # If no hyphen, assume last digit is DV
            if len(clean_ruc) >= 7:
                ruc_number = clean_ruc[:-1]
                check_digit = clean_ruc[-1]
            else:
                return False, "RUC incomplete: must include the check digit."

        # Validate length
        if len(ruc_number) < 6 or len(ruc_number) > 8:
            return False, "RUC must have between 6 and 8 digits"

        # Calculate expected check digit
        calculated_digit = cls._calculate_check_digit(ruc_number)

        # If a DV was provided, validate it
        if check_digit is not None:
            if str(calculated_digit) != check_digit:
                return (
                    False,
                    f"Invalid check digit. "
                    f"Expected: {calculated_digit}, "
                    f"Received: {check_digit}",
                )

        return True, ""

    @classmethod
    def _calculate_check_digit(cls, ruc_number):
        """
        Calculate check digit using Module 11 (Paraguay SET)

        Algorithm:
        1. Pad RUC with leading zeros to 9 digits
        2. Apply weights [2,3,4,5,6,7,8,9] cyclically from left to right
        3. Find DV (0-9) such that the total weighted sum (including DV)
           mod 11 == 0

        Verification: RUC 80012345 -> DV 6, RUC 4588955 -> DV 1

        Args:
            ruc_number (str): RUC number without check digit

        Returns:
            int: Calculated check digit
        """
        # Pad with leading zeros to 9 digits
        ruc_padded = ruc_number.zfill(9)

        # Calculate partial weighted sum (9 digits of RUC)
        partial_sum = 0
        for i, digit in enumerate(ruc_padded):
            partial_sum += int(digit) * cls.WEIGHTS[i % 8]

        # DV is at position 9 (index 9), with weight = WEIGHTS[9 % 8] = WEIGHTS[1] = 3
        # Find DV such that (partial_sum + DV * 3) % 11 == 0
        # Using modular inverse: inv(3, 11) = 4 (since 3*4 = 12 ≡ 1 mod 11)
        remainder = partial_sum % 11
        dv = ((11 - remainder) % 11 * 4) % 11

        # DV must be a single digit (0-9)
        if dv >= 10:
            dv = 0

        return dv

    @classmethod
    def format_ruc(cls, ruc, include_dv=True):
        """
        Format RUC for standardized display

        Args:
            ruc (str): RUC to be formatted
            include_dv (bool): If True, includes the check digit

        Returns:
            str: Formatted RUC (XXXXXXX-D)
        """
        # Clean format
        clean_ruc = re.sub(r"[^\d]", "", ruc)

        if len(clean_ruc) < 6:
            return ruc  # Return original if too short

        # If last digit could be DV, separate
        if len(clean_ruc) >= 7:
            ruc_number = clean_ruc[:-1]
            existing_dv = clean_ruc[-1]

            # Validate if DV is correct
            calculated_dv = cls._calculate_check_digit(ruc_number)

            if str(calculated_dv) == existing_dv:
                # DV is correct, use the provided one
                if include_dv:
                    return f"{ruc_number}-{existing_dv}"
                else:
                    return ruc_number
            else:
                # DV incorrect or doesn't exist, calculate
                if include_dv:
                    new_dv = cls._calculate_check_digit(clean_ruc)
                    return f"{clean_ruc}-{new_dv}"
                else:
                    return clean_ruc
        else:
            # Without DV, calculate
            if include_dv:
                dv = cls._calculate_check_digit(clean_ruc)
                return f"{clean_ruc}-{dv}"
            else:
                return clean_ruc

    @classmethod
    def get_ruc_number(cls, ruc):
        """
        Extract only the RUC number (without DV)

        Args:
            ruc (str): Complete RUC

        Returns:
            str: RUC number without DV
        """
        clean_ruc = re.sub(r"[^\d]", "", ruc)

        if not clean_ruc:
            return ""

        # If has DV (7-9 digits), remove last digit
        if len(clean_ruc) >= 7:
            # Check if last digit is a valid DV
            ruc_number = clean_ruc[:-1]
            check_digit = clean_ruc[-1]
            calculated_digit = cls._calculate_check_digit(ruc_number)

            if str(calculated_digit) == check_digit:
                return ruc_number
            else:
                # Not a valid DV, return full
                return clean_ruc
        else:
            return clean_ruc

    @classmethod
    def get_check_digit(cls, ruc):
        """
        Get the check digit from the RUC

        Args:
            ruc (str): RUC (with or without DV)

        Returns:
            str: Check digit
        """
        ruc_number = cls.get_ruc_number(ruc)
        return str(cls._calculate_check_digit(ruc_number))

    @classmethod
    def is_valid_format(cls, ruc):
        """
        Check if RUC format is valid (without validating DV)

        Args:
            ruc (str): RUC to validate

        Returns:
            bool: True if format is valid
        """
        if not ruc:
            return False

        # RUC must contain only digits and optionally one hyphen
        if not re.match(r"^[\d-]+$", ruc):
            return False

        clean_ruc = re.sub(r"[^\d]", "", ruc)

        # Must have between 6 and 9 digits (6-8 for RUC + 1 for DV)
        if len(clean_ruc) < 6 or len(clean_ruc) > 9:
            return False

        return True

    @classmethod
    def normalize(cls, ruc):
        """
        Normalize RUC to standardized format

        Args:
            ruc (str): RUC in any format

        Returns:
            str: Normalized RUC (XXXXXXX-D)
        """
        if not ruc:
            return ""

        is_valid, error = cls.validate(ruc)

        if not is_valid:
            _logger.warning("Invalid RUC: %s - %s", ruc, error)
            return ruc  # Return original if invalid

        return cls.format_ruc(ruc, include_dv=True)
