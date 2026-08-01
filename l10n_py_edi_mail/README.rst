=======================
l10n_py_edi_mail
=======================

EDI Email Notifications for Paraguay
====================================

This module provides automatic email notifications for EDI documents.

Features
--------

* Automatic email when EDI document is accepted
* Automatic email when EDI document is rejected
* Automatic email when EDI document is cancelled
* Attach XML and KuDE PDF to emails
* Per-document control to disable auto-send
* Cron job to retry failed notifications

Configuration
-------------

1. Go to *Settings > Users & Companies > Companies*
2. Select your company
3. Configure the EDI notification partner (optional)
4. Enable/disable auto-send per document

Usage
-----

When an EDI document changes status to accepted, rejected, or cancelled,
an email is automatically sent to:

- The customer (partner) if they have an email
- The company notification contact (if configured)

The email includes:

- Document details (CDC, date, amount)
- Error information (for rejected documents)
- XML attachment
- KuDE PDF attachment

Contributors
------------

* Odoo Community Association (OCA)

Maintainers
-----------

This module is maintained by the Odoo Community Association (OCA).