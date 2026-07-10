from pydantic import BaseModel


class MigrateImportResponse(BaseModel):
    success: bool = True
    counts: dict
    message: str = "导入成功"
