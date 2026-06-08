=======================
l10n_py_cert_expiry
=======================

Certificate Expiry Notifications for Paraguay
====================================

This module provides automatic notifications when SIFEN certificates are about to expire.

Features
--------

* Daily check of certificate expiry dates
* Automatic email notification when certificate is about to expire
* Configurable warning period (default: 30 days)
* Warning message on company form for expired certificates
* No duplicate notifications on the same day

Configuration
-------------

1. Go to *Settings > Users & Companies > Companies*
2. Select your company
3. Configure the certificate expiry warning days (default: 30)
4. Set a certificate notification contact (optional)

Usage
-----

The module runs a daily cron job that checks all company certificates.
When a certificate is within the warning period, an email is sent to:
- The configured notification contact, or
- The company partner if no contact is configured

A warning message is also posted on the company record for:
- Certificates that have already expired
- Certificates within the warning period

Contributors
------------

* Odoo Community Association (OCA)

Maintainers
-----------

This module is maintained by the Odoo Community Association (OCA).