"""验收清单领域服务：签收验收项、巡检联动门禁、交场前置检查。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class ChecklistService(BaseModuleService):
    MODULE = "checklist"
    ENTITY = "验收项"
    OPERATION_TERM = "签收验收"
    LIST_FIELDS = ["验收条目", "验收标准", "负责班组", "完成时间", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["验收条目", "验收标准", "负责班组", "完成时间"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"签收验收": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["safety", "handover"]

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "签收验收":
            validation = exhibition.validate_checklist_signoff(entry_id)
            if not validation["ok"]:
                return False, validation["reason"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        unsigned = [r for r in rows if r.get("status") != "已确认"]
        base["signed_count"] = len(confirmed)
        base["unsigned_count"] = len(unsigned)
        return base