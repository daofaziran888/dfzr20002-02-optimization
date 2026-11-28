"""家具配置领域服务：家具类型校验、数量需求与展位面积匹配检查、展位关联。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store


class FurnitureService(BaseModuleService):
    MODULE = "furniture"
    ENTITY = "家具方案"
    OPERATION_TERM = "确认配置"
    LIST_FIELDS = ["家具类型", "摆放位置", "数量需求", "风格色调", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["家具类型", "摆放位置", "数量需求"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认配置": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["booth", "design"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            qty = int(str(values.get("数量需求", "0")).strip())
            if qty <= 0:
                errors.append("数量需求必须大于0")
        except (ValueError, AttributeError):
            errors.append("数量需求格式不正确")
        # 跨模块校验：家具备注说明应对应有效展位
        remark = str(values.get("备注说明", "")).strip()
        if remark and remark.startswith("BOOT-"):
            booth = store.find_booth(remark)
            if booth is None:
                errors.append(f"展位 {remark} 不存在，请先登记展位")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认配置":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "家具方案不存在"
            remark = str(entry.get("备注说明", ""))
            if remark and remark.startswith("BOOT-"):
                # 检查该展位是否有已确认的设计方案
                designs = store.rows("design")
                has_design = any(
                    d.get("status") == "已确认" and str(d.get("备注说明", "")) == remark
                    for d in designs
                )
                if not has_design:
                    return False, f"展位 {remark} 设计方案尚未审核，家具配置不可确认"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = self.related_rows("furniture")
        if rows:
            base["total_furniture_count"] = sum(
                int(str(r.get("数量需求", "0")).strip()) for r in rows
            )
        base["booth_linked"] = sum(
            1 for r in rows if str(r.get("备注说明", "")).startswith("BOOT-")
        )
        return base