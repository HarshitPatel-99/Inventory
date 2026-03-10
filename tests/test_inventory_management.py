from datetime import date, timedelta

from inventory_management import InventoryManager, Product, seed_ram_and_company_catalog


def test_stock_calculation_and_sales_guard(tmp_path):
    db_path = tmp_path / "test_inventory.db"
    manager = InventoryManager(str(db_path))
    manager.add_product(Product("SKU-1", "Sample Door", "Doors", "piece"))

    manager.record_supply("SKU-1", 10, 1000)
    manager.record_sale("SKU-1", 3, 1300)

    assert manager.get_available_stock("SKU-1") == 7

    try:
        manager.record_sale("SKU-1", 8, 1300)
        assert False, "Expected ValueError when selling beyond available stock"
    except ValueError as exc:
        assert "Insufficient stock" in str(exc)


def test_weekly_report_values(tmp_path):
    db_path = tmp_path / "test_inventory.db"
    manager = InventoryManager(str(db_path))
    seed_ram_and_company_catalog(manager)

    today = date.today()
    manager.record_supply("PWD-FLUSH-32", 20, 2500, today - timedelta(days=5))
    manager.record_sale("PWD-FLUSH-32", 5, 3200, today - timedelta(days=2))

    report = manager.generate_report("weekly", today)

    assert report["totals"]["SUPPLY"] == 20
    assert report["totals"]["SALE"] == 5
    assert report["totals"]["SALE_VALUE"] == 16000
