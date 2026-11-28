"""搭建物料领域服务：物料配额数量校验、领用时检查设计方案是否已审核。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class MaterialService(BaseModuleService):
    MODULE = "material"
    ENTITY = "物料"
    OPERATION_TERM = "领用物料"
    LIST_FIELDS = ["物料名称", "规格型号", "配额数量", "所属施工", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["物料名称", "规格型号", "配额数量"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"领用物料": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["design"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            qty = int(str(values.get("配额数量", "0")).strip())
            if qty <= 0:
                errors.append("配额数量必须大于0")
        except (ValueError, AttributeError):
            errors.append("配额数量格式不正确")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "领用物料":
            material = store.find(self.MODULE, entry_id)
            if material is None:
                return False, "物料不存在"
            # 检查设计方案是否已审核
            designs = store.rows("design")
            confirmed_designs = [d for d in designs if d.get("status") == "已确认"]
            if not confirmed_designs:
                return False, "暂无已审核的设计方案，不能领用物料"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = self.related_rows("material")
        total_qty = sum(int(str(r.get("配额数量", "0")).strip()) for r in rows)
        base["total_quota"] = total_qty
        return base