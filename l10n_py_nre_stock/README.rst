===========================
l10n_py_nre_stock
===========================

.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

| This module integrates NRE (Nota de Remisión Electrónica, document type 7)
  with Odoo's Inventory management (stock.picking).
| When an NRE is created, a stock picking can be automatically generated
  to track the physical movement of goods.

**Features**

* Link NRE documents to stock.picking records
* Auto-compute source/destination warehouse from company settings
* Create stock moves from NRE invoice lines
* View linked pickings directly from the NRE form
* Wizard for batch creation of pickings from multiple NREs

**Configuration**

#. Go to *Settings > Companies > [Your Company]* and set:
   * Default Source Warehouse
   * Default Destination Warehouse
#. On NRE documents (type 7), the warehouse fields will be auto-filled
#. Click "Create Stock Picking" to generate the picking

**Dependencies**

* ``l10n_py_edi_base`` — Base EDI functionality
* ``stock`` — Odoo Inventory module

**Usage**

#. Create an NRE (document type 7) with products
#. Configure the default warehouse on the company
#. Click "Create Stock Picking" in the NRE form
#. The picking is created with stock moves from the NRE lines
#. Confirm and process the picking in Inventory app

**Repository**

https://github.com/OCA/l10n-paraguay

**Maintainer**

| This module is maintained by the Odoo Community Association (OCA).
| OCA, or the Odoo Community Association, is a nonprofit organization whose
  mission is to support the collaborative development of Odoo features and
  promote the widespread use of Odoo.