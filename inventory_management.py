"""Inventory management solution for Ram & Company.

This module provides a small, self-contained inventory management backend
powered by SQLite. It tracks products, stock movements, and sales so the
manager can quickly answer stock availability enquiries and generate weekly
or monthly analysis reports.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    unit: str


class InventoryManager:
    """Manage inventory, supply, and sales information."""

    def __init__(self, db_path: str = "inventory.db") -> None:
        self.db_path = db_path
        self._create_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _create_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    movement_type TEXT NOT NULL CHECK (movement_type IN ('SUPPLY', 'SALE')),
                    quantity REAL NOT NULL CHECK (quantity > 0),
                    unit_price REAL,
                    movement_date TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                """
            )

    def add_product(self, product: Product) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO products (sku, name, category, unit)
                VALUES (?, ?, ?, ?)
                """,
                (product.sku, product.name, product.category, product.unit),
            )

    def record_supply(
        self,
        sku: str,
        quantity: float,
        unit_price: float | None = None,
        movement_date: date | None = None,
        notes: str | None = None,
    ) -> None:
        self._record_movement(
            sku=sku,
            movement_type="SUPPLY",
            quantity=quantity,
            unit_price=unit_price,
            movement_date=movement_date,
            notes=notes,
        )

    def record_sale(
        self,
        sku: str,
        quantity: float,
        unit_price: float,
        movement_date: date | None = None,
        notes: str | None = None,
    ) -> None:
        available = self.get_available_stock(sku)
        if quantity > available:
            raise ValueError(
                f"Insufficient stock for {sku}. Available: {available}, requested: {quantity}."
            )
        self._record_movement(
            sku=sku,
            movement_type="SALE",
            quantity=quantity,
            unit_price=unit_price,
            movement_date=movement_date,
            notes=notes,
        )

    def _record_movement(
        self,
        sku: str,
        movement_type: str,
        quantity: float,
        unit_price: float | None,
        movement_date: date | None,
        notes: str | None,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")

        movement_date = movement_date or date.today()
        with self._connect() as connection:
            product_row = connection.execute(
                "SELECT id FROM products WHERE sku = ?", (sku,)
            ).fetchone()
            if product_row is None:
                raise ValueError(f"Product with SKU '{sku}' does not exist.")

            connection.execute(
                """
                INSERT INTO stock_movements (
                    product_id, movement_type, quantity, unit_price, movement_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_row["id"],
                    movement_type,
                    quantity,
                    unit_price,
                    movement_date.isoformat(),
                    notes,
                ),
            )

    def get_available_stock(self, sku: str) -> float:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN m.movement_type = 'SUPPLY' THEN m.quantity ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN m.movement_type = 'SALE' THEN m.quantity ELSE 0 END), 0)
                    AS available_stock
                FROM products p
                LEFT JOIN stock_movements m ON p.id = m.product_id
                WHERE p.sku = ?
                GROUP BY p.id
                """,
                (sku,),
            ).fetchone()

            if row is None:
                raise ValueError(f"Product with SKU '{sku}' does not exist.")
            return float(row["available_stock"])

    def stock_snapshot(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT
                    p.sku,
                    p.name,
                    p.category,
                    p.unit,
                    COALESCE(SUM(CASE WHEN m.movement_type = 'SUPPLY' THEN m.quantity ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN m.movement_type = 'SALE' THEN m.quantity ELSE 0 END), 0)
                    AS available_stock
                FROM products p
                LEFT JOIN stock_movements m ON p.id = m.product_id
                GROUP BY p.id
                ORDER BY p.name
                """
            ).fetchall()

    def generate_report(self, period: str = "weekly", reference_date: date | None = None) -> dict:
        if period not in {"weekly", "monthly"}:
            raise ValueError("period must be either 'weekly' or 'monthly'")

        reference_date = reference_date or date.today()

        if period == "weekly":
            start_date = reference_date - timedelta(days=6)
        else:
            start_date = reference_date.replace(day=1)

        with self._connect() as connection:
            summary = connection.execute(
                """
                SELECT
                    movement_type,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM(CASE WHEN movement_type = 'SALE' THEN quantity * unit_price ELSE 0 END), 0) AS total_sale_value
                FROM stock_movements
                WHERE movement_date BETWEEN ? AND ?
                GROUP BY movement_type
                """,
                (start_date.isoformat(), reference_date.isoformat()),
            ).fetchall()

            product_breakdown = connection.execute(
                """
                SELECT
                    p.sku,
                    p.name,
                    m.movement_type,
                    SUM(m.quantity) AS quantity,
                    SUM(CASE WHEN m.movement_type = 'SALE' THEN m.quantity * m.unit_price ELSE 0 END) AS sale_value
                FROM stock_movements m
                JOIN products p ON p.id = m.product_id
                WHERE m.movement_date BETWEEN ? AND ?
                GROUP BY p.id, m.movement_type
                ORDER BY p.name
                """,
                (start_date.isoformat(), reference_date.isoformat()),
            ).fetchall()

        totals = {"SUPPLY": 0.0, "SALE": 0.0, "SALE_VALUE": 0.0}
        for row in summary:
            totals[row["movement_type"]] = float(row["total_quantity"])
            if row["movement_type"] == "SALE":
                totals["SALE_VALUE"] = float(row["total_sale_value"])

        return {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": reference_date.isoformat(),
            "totals": totals,
            "by_product": [dict(row) for row in product_breakdown],
        }


def seed_ram_and_company_catalog(manager: InventoryManager) -> None:
    """Seed common furniture-store inventory categories for Ram & Company."""
    products: Iterable[Product] = [
        Product("PWD-FLUSH-32", "Pinewood Flush Door 32mm", "Pinewood Flush Doors", "piece"),
        Product("HWD-FLUSH-35", "Hardwood Flush Door 35mm", "Hardwood Flush Doors", "piece"),
        Product("HW-LOCK-01", "Main Door Lock Set", "Door Locks", "set"),
        Product("DS-NYLON-01", "Nylon Door Screen", "Door Screen", "piece"),
        Product("PLY-19-01", "Plywood 19mm", "Plywood", "sheet"),
        Product("BB-18-01", "Blockboard 18mm", "Blockboards", "sheet"),
        Product("ADH-WD-01", "Wood Adhesive 1L", "Wood Adhesive", "can"),
        Product("TK-BEAD-01", "Teak Wood Beading", "Teak Wood Beading", "meter"),
        Product("HW-HINGE-01", "Stainless Steel Hinges", "Hardware Items", "set"),
    ]

    for product in products:
        manager.add_product(product)


def print_report(report: dict) -> None:
    title = report["period"].capitalize()
    print(f"\n{title} Report ({report['start_date']} to {report['end_date']})")
    print("-" * 60)
    print(f"Total Supply Quantity : {report['totals']['SUPPLY']}")
    print(f"Total Sales Quantity  : {report['totals']['SALE']}")
    print(f"Total Sales Value     : ₹{report['totals']['SALE_VALUE']:.2f}")
    print("\nProduct Breakdown:")
    for row in report["by_product"]:
        label = "Sales" if row["movement_type"] == "SALE" else "Supply"
        value_text = f", Value: ₹{(row['sale_value'] or 0):.2f}" if row["movement_type"] == "SALE" else ""
        print(f"  - {row['sku']} | {row['name']} | {label}: {row['quantity']}{value_text}")


def demo() -> None:
    manager = InventoryManager()
    seed_ram_and_company_catalog(manager)

    today = date.today()
    manager.record_supply("PWD-FLUSH-32", 20, 2700, today - timedelta(days=5), "Received from Supplier A")
    manager.record_supply("HWD-FLUSH-35", 12, 3600, today - timedelta(days=4), "Received from Supplier B")
    manager.record_supply("PLY-19-01", 50, 1800, today - timedelta(days=3), "Truck lot 14")
    manager.record_supply("HW-LOCK-01", 40, 850, today - timedelta(days=3))

    manager.record_sale("PWD-FLUSH-32", 4, 3200, today - timedelta(days=2), "Customer: Green Homes")
    manager.record_sale("HW-LOCK-01", 8, 1100, today - timedelta(days=1), "Counter sales")

    print("Current Stock Snapshot")
    print("-" * 60)
    for row in manager.stock_snapshot():
        print(f"{row['sku']:<12} | {row['name']:<30} | {row['available_stock']} {row['unit']}")

    print_report(manager.generate_report("weekly", today))
    print_report(manager.generate_report("monthly", today))


if __name__ == "__main__":
    demo()
