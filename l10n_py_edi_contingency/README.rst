=====================
l10n_py_edi_contingency
=====================

This module enables offline/contingency operation for EDI in Paraguay.

When the internet connection is unavailable or SIFEN is unreachable, companies
can continue issuing electronic documents using physical contingency booklets
( cuadernillos ) provided by SET (Subsecretaria de Estado de Tributacion).

Features
========

* Contingency Booklet Management: Register and track SET physical booklets with
  their number ranges.

* Automatic Number Assignment: When contingency mode is activated, the system
  assigns the next available number from the selected booklet.

* Offline Document Generation: Creates documents in SET contingency format
  without requiring SIFEN connection.

* Automatic Sync: When connection is restored, the system automatically syncs
  contingency documents to SIFEN to obtain real CDC and replace the provisional
  documents.

* Queue Management: Tracks all pending contingency documents and their sync
  status.

Usage
=====

1. Register Booklets: Go to Paraguay EDI > Contingency Booklets and create
   entries for each physical booklet from SET.

2. Activate Contingency: When SIFEN is unavailable, select the invoices you
   want to issue and click Activate Contingency. Assign a booklet to use.

3. Issue Documents: The invoices will be numbered from the physical booklet and
   marked as contingency_pending. They can be printed or exported as needed.

4. Sync When Online: When internet connection is restored, the system will
   automatically sync pending contingency documents to SIFEN, obtaining real CDC
   numbers and updating the XML.

Configuration
=============

No special configuration is required beyond registering the contingency booklets
provided by SET.

Requirements
============

* l10n_py_edi_base
* l10n_py_edi_sifen

Bug Tracker
===========

Bugs are tracked on GitHub Issues. In case of trouble, please check there if
your issue has already been reported. If you spotted it first, help us smash
it by providing a detailed and welcomed feedback.

Credits
=======

Contributors
------------

* Odoo Community Association (OCA)

Maintainers
-----------

This module is maintained by the OCA.

This module is part of the OCA/l10n-paraguay project on GitHub.

You are welcome to contribute.