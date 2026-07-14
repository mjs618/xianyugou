from pathlib import Path

import app.schemas as schemas
from app.main import app


APP_DIR = Path(__file__).parent / "app"

EXPECTED_EXPORTS = {
    "ORMBase",
    "CustomerOut",
    "CustomerCreate",
    "CustomerUpdate",
    "TransactionOut",
    "TransactionCreate",
    "TransactionUpdate",
    "StatusChange",
    "AfterSalesOut",
    "AfterSalesCreate",
    "AfterSalesUpdate",
    "RebateOut",
    "RebateStatusChange",
    "RebateBatchPay",
    "OperatingExpenseOut",
    "OperatingExpenseCreate",
    "OperatingExpenseUpdate",
    "ProductTemplateOut",
    "ProductTemplateCreate",
    "ProductTemplateUpdate",
    "SettingsOut",
    "SettingsUpdate",
    "OperationLogOut",
    "LogListResponse",
    "MigrateImportResponse",
    "AttachmentOut",
    "AttachmentBatchRequest",
    "XianyuAccountCreate",
    "XianyuAccountUpdate",
    "XianyuAccountOut",
    "XianyuAccountTestResult",
    "CookieCloudConfigStatus",
    "XianyuSyncResult",
    "XianyuItemSyncResult",
    "XianyuItemOut",
    "XianyuItemImportRequest",
    "XianyuItemImportResult",
    "XianyuOrderOut",
    "MessageResponse",
    "HealthResponse",
    "TokenStatus",
    "VerifyTokenRequest",
    "VerifyTokenResponse",
    "AuthError",
    "AccountMetrics",
    "BackupMetrics",
    "MetricsResponse",
    "SyncMetrics",
    "CustomerTagCreate",
    "CustomerTagsUpdate",
    "MailRecordCreate",
    "WarrantyExtend",
    "WarrantyEndEarly",
    "BackupInfo",
    "BackupListResponse",
    "RestoreRequest",
    "RestoreResponse",
}

EXPECTED_MODULES = {
    "CustomerOut": "app.schemas.customers",
    "TransactionOut": "app.schemas.transactions",
    "AfterSalesOut": "app.schemas.aftersales",
    "RebateOut": "app.schemas.rebates",
    "OperatingExpenseOut": "app.schemas.expenses",
    "ProductTemplateOut": "app.schemas.product_templates",
    "SettingsOut": "app.schemas.settings",
    "OperationLogOut": "app.schemas.audit",
    "MigrateImportResponse": "app.schemas.migrate",
    "AttachmentOut": "app.schemas.attachments",
    "XianyuAccountOut": "app.schemas.xianyu",
    "HealthResponse": "app.schemas.common",
    "TokenStatus": "app.schemas.auth",
    "VerifyTokenRequest": "app.schemas.auth",
    "VerifyTokenResponse": "app.schemas.auth",
    "AuthError": "app.schemas.auth",
    "AccountMetrics": "app.schemas.metrics",
    "BackupMetrics": "app.schemas.metrics",
    "MetricsResponse": "app.schemas.metrics",
    "SyncMetrics": "app.schemas.metrics",
}


def test_schema_package_has_exact_compatibility_exports():
    assert set(schemas.__all__) == EXPECTED_EXPORTS
    assert all(hasattr(schemas, name) for name in EXPECTED_EXPORTS)
    assert not (APP_DIR / "schemas.py").exists()


def test_schema_classes_belong_to_domain_modules():
    for name, module in EXPECTED_MODULES.items():
        assert getattr(schemas, name).__module__ == module


def test_critical_field_constraints_are_preserved():
    expense_schema = schemas.OperatingExpenseCreate.model_json_schema()
    template_schema = schemas.ProductTemplateCreate.model_json_schema()
    attachment_schema = schemas.AttachmentBatchRequest.model_json_schema()

    assert expense_schema["properties"]["amount"]["exclusiveMinimum"] == 0
    assert template_schema["properties"]["warranty_days"]["minimum"] == 0
    assert attachment_schema["properties"]["ids"]["maxItems"] == 50


def test_fastapi_openapi_still_builds_with_public_schema_names():
    components = app.openapi()["components"]["schemas"]
    for name in (
        "CustomerOut",
        "TransactionOut",
        "SettingsOut",
        "AttachmentOut",
        "XianyuAccountOut",
    ):
        assert name in components
