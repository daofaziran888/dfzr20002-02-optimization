"""布展排期领域服务：排期校验、撤展与布展时间逻辑检查、冲突检测输出。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService


class ScheduleService(BaseModuleService):
    MODULE = "schedule"
    ENTITY = "排期计划"
    OPERATION_TERM = "发布排期"
    LIST_FIELDS = ["活动名称", "布展起始", "撤展截止", "值班安排", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["活动名称", "布展起始", "撤展截止"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"发布排期": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["transport", "construction"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        setup = str(values.get("布展起始", "")).strip()
        teardown = str(values.get("撤展截止", "")).strip()
        if setup and teardown and setup >= teardown:
            errors.append("布展起始日期必须早于撤展截止日期")
        return errors

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = self.related_rows("schedule")
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        base["active_schedules"] = len(confirmed)
        return base