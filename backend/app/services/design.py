"""方案设计领域服务：搭建合规校验、用电负荷与展位关联、审核方案后联动物料领用。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DesignService(BaseModuleService):
    MODULE = "design"
    ENTITY = "设计方案"
    OPERATION_TERM = "审核方案"
    LIST_FIELDS = ["设计风格", "结构材料", "搭建高度", "用电负荷", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["设计风格", "结构材料", "搭建高度", "用电负荷"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"审核方案": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["booth", "electrical", "material"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            height = float(str(values.get("搭建高度", "0")).replace("米", "").replace("m", "").strip())
            if height <= 0:
                errors.append("搭建高度必须大于0")
        except (ValueError, AttributeError):
            errors.append("搭建高度格式不正确")
        try:
            load = float(str(values.get("用电负荷", "0")).replace("kW", "").replace("W", "").strip())
            if load <= 0:
                errors.append("用电负荷必须大于0")
        except (ValueError, AttributeError):
            errors.append("用电负荷格式不正确")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "审核方案":
            design = store.find(self.MODULE, entry_id)
            if design is None:
                return False, "设计方案不存在"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        total_load = sum(
            float(str(r.get("用电负荷", "0")).replace("kW", "").replace("W", "").strip())
            for r in confirmed
            if str(r.get("用电负荷", "0")).replace("kW", "").replace("W", "").strip()
        )
        base["total_design_load_kw"] = total_load
        return base