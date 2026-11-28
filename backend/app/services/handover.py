"""交场确认领域服务：验收清单全面签收后才能交场，可反查执行历史。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class HandoverService(BaseModuleService):
    MODULE = "handover"
    ENTITY = "交场单"
    OPERATION_TERM = "完成交场"
    LIST_FIELDS = ["交出班组", "接收人员", "遗留事项", "交接时刻", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["交出班组", "接收人员", "遗留事项", "交接时刻"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"完成交场": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["checklist", "safety", "construction"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        booth_no = str(values.get("遗留事项", "")).strip()
        if booth_no:
            booth = store.find_booth(booth_no)
            if booth is None:
                errors.append(f"展位 {booth_no} 不存在，请先登记展位")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "完成交场":
            validation = exhibition.validate_handover(entry_id)
            if not validation["ok"]:
                return False, validation["reason"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        confirmed = sum(1 for r in rows if r.get("status") == "已确认")
        base["completed_handovers"] = confirmed
        return base