from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app


ROUTER_DIR = Path(__file__).parent / "app" / "routers"
MAIN = Path(__file__).parent / "app" / "main.py"

EXPECTED_ROUTES = {
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("GET", "/api/product-templates"),
    ("POST", "/api/product-templates"),
    ("PATCH", "/api/product-templates/{tpl_id}"),
    ("DELETE", "/api/product-templates/{tpl_id}"),
    ("POST", "/api/product-templates/{tpl_id}/toggle"),
    ("GET", "/api/finance/overview"),
    ("GET", "/api/finance/products"),
    ("GET", "/api/finance/customers"),
    ("GET", "/api/finance/overview-by-range"),
    ("GET", "/api/finance/trend"),
    ("GET", "/api/finance/monthly-comparison"),
    ("GET", "/api/finance/new-customer-count"),
    ("GET", "/api/finance/channel-breakdown"),
    ("POST", "/api/finance/backfill-cost"),
    ("GET", "/api/expenses"),
    ("POST", "/api/expenses"),
    ("PATCH", "/api/expenses/{expense_id}"),
    ("DELETE", "/api/expenses/{expense_id}"),
    ("GET", "/api/operation-logs"),
    ("DELETE", "/api/operation-logs"),
    ("POST", "/api/migrate/import"),
    ("GET", "/api/migrate/export"),
}


def test_split_domain_route_surface_is_preserved():
    prefixes = (
        "/api/settings",
        "/api/product-templates",
        "/api/finance",
        "/api/expenses",
        "/api/operation-logs",
        "/api/migrate",
    )
    actual = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(prefixes)
        for method in route.methods
    }

    assert actual == EXPECTED_ROUTES


def test_each_domain_has_one_router_module():
    expected_files = {
        "settings.py",
        "product_templates.py",
        "finance.py",
        "expenses.py",
        "audit.py",
        "migrate.py",
    }
    assert expected_files <= {path.name for path in ROUTER_DIR.glob("*.py")}

    settings_source = (ROUTER_DIR / "settings.py").read_text(encoding="utf-8")
    for forbidden in (
        "/api/product-templates",
        "/api/finance",
        "/api/expenses",
        "/api/operation-logs",
        "/api/migrate",
        "product_template_service",
        "finance_service",
        "expense_service",
        "audit_service",
        "migrate_service",
    ):
        assert forbidden not in settings_source

    main_source = MAIN.read_text(encoding="utf-8")
    assert "settings_router_module" not in main_source
