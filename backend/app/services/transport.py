"""展品运输领域服务：运输方式校验、预计到达与排期冲突检测。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class TransportService(BaseModuleService):
    MODULE = "transport"
    ENTITY = "运输单"
    OPERATION_TERM = "确认运输"
    LIST_FIELDS = ["展品名称", "运输方式", "预计到达", "保价金额", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["展品名称", "运输方式", "预计到达"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认运输": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["schedule"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        method = str(values.get("运输方式", "")).strip()
        if method not in ("公路", "铁路", "航空", "海运", "快递"):
            errors.append(f"运输方式 {method} 不在允许范围")
        try:
            insured = float(str(values.get("保价金额", "0")).replace("万元", "").replace(",", "").strip())
            if insured < 0:
                errors.append("保价金额不能为负数")
        except (ValueError, AttributeError):
            pass
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认运输":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "运输单不存在"
            conflicts = [c for c in exhibition.detect_schedule_conflicts()
                        if str(c.get("transport_id")) == str(entry_id)]
            if conflicts:
                return False, conflicts[0]["conflict"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = self.related_rows("transport")
        methods: dict[str, int] = {}
        for r in rows:
            m = str(r.get("运输方式", ""))
            methods[m] = methods.get(m, 0) + 1
        base["by_method"] = methods
        return base