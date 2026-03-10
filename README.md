# Ram & Company Inventory Management

A lightweight Python + SQLite inventory management solution tailored for **Ram & Company** (furniture and door materials store).

## What this solution supports

- Product catalog for:
  - Pinewood flush doors
  - Hardwood flush doors
  - Hardware items
  - Door screen
  - Door locks
  - Plywood
  - Blockboards
  - Wood adhesive
  - Teak wood beading
- Real-time stock availability check (`get_available_stock` and `stock_snapshot`)
- Supply entry tracking
- Sales entry tracking with stock validation (prevents overselling)
- Weekly and monthly analysis reports:
  - Total supplied quantity
  - Total sold quantity
  - Total sales value
  - Product-level movement breakdown

## Run demo

```bash
python inventory_management.py
```

This seeds the catalog, inserts sample supply/sales movements, prints current stock, and generates weekly/monthly reports.

## Run tests

```bash
python -m pytest -q
```

## Core API

- `InventoryManager.add_product(product)`
- `InventoryManager.record_supply(...)`
- `InventoryManager.record_sale(...)`
- `InventoryManager.get_available_stock(sku)`
- `InventoryManager.stock_snapshot()`
- `InventoryManager.generate_report(period="weekly" | "monthly")`

