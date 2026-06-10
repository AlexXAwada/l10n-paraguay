=======================
l10n_py_account_sequence
=======================

Account Authorization Sequences for Paraguay
=============================================

This module extends account.authorization to support multiple authorization
series (timbrados) with different series codes (001, 002, etc.).

Features
--------

* Multiple authorization series per company
* Series code (3-digit) for each authorization
* Default series selection
* Sequence tracking per authorization
* CDC invalidation when authorization is deactivated
* Unique series code per company

Usage
-----

1. Go to *Invoicing > Configuration > Authorizations*
2. Create a new authorization with a series code (e.g., "001")
3. Mark as "Default Series" if it should be used by default
4. Each authorization maintains its own sequence

When multiple authorizations exist, the system ensures:
- Series codes are unique per company
- Only one authorization can be default per company
- CDC numbers are invalidated when authorization is deactivated

Contributors
------------

* Odoo Community Association (OCA)

Maintainers
-----------

This module is maintained by the Odoo Community Association (OCA).