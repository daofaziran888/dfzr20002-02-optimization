"""安全巡检领域服务：巡检状态联动验收清单签收和交场门禁。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SafetyService(BaseModuleService):
    MODULE = "safety"
    ENTITY = "巡检记录"
    OPERATION_TERM = "关闭隐患"
    LIST_FIELDS = ["检查点位", "隐患等级", "整改措施", "复查日期", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["检查点位", "隐患等级", "整改措施"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"关闭隐患": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["checklist", "handover"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        level = str(values.get("隐患等级", "")).strip()
        if level not in ("轻微", "一般", "严重", "重大"):
            errors.append(f"隐患等级 {level} 不在允许范围（轻微/一般/严重/重大）")
        return errors

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        by_level: dict[str, int] = {}
        for row in rows:
            level = str(row.get("隐患等级", "未分类"))
            by_level[level] = by_level.get(level, 0) + 1
        base["by_danger_level"] = by_level
        return base