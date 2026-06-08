=======================
l10n_py_edi_summary
=======================

EDI Daily Summary and Manual Sync Interface
============================================

This module provides daily EDI summary reporting and manual sync interface.

Features
--------

* Daily summary statistics for EDI operations
* Email notification with daily summary
* Manual sync interface for checking status and retrying
* Document type breakdown (FE, AFE, NCE, NDE, NRE)
* Top errors tracking
* Success rate monitoring

Configuration
-------------

1. Go to *EDI > Summary* to view daily statistics
2. Use *EDI > Manual Sync* to check status or retry documents
3. Configure email notifications in company settings

Usage
-----

Daily Summary
~~~~~~~~~~~~~

The system automatically generates a daily summary at the end of each day,
including:

- Total documents processed
- Accepted/rejected/pending counts
- Document type breakdown
- Top errors of the day
- Success rate

Manual Sync
~~~~~~~~~~

Use the manual sync interface to:

- Check status of pending documents
- Retry sending rejected documents
- Batch retry with CDC recalculation

Contributors
------------

* Odoo Community Association (OCA)

Maintainers
-----------

This module is maintained by the Odoo Community Association (OCA).