"""导视系统领域服务：指示内容规范校验、安装点位重复检查、展位关联。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store


class SignageService(BaseModuleService):
    MODULE = "signage"
    ENTITY = "导视牌"
    OPERATION_TERM = "确认导视"
    LIST_FIELDS = ["指示内容", "安装点位", "尺寸规格", "发光类型", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["指示内容", "安装点位", "尺寸规格"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认导视": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["electrical", "booth"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        location = str(values.get("安装点位", "")).strip()
        if location:
            existing = store.rows(self.MODULE)
            for s in existing:
                if str(s.get("安装点位", "")) == location and s.get("status") != "已撤回":
                    errors.append(f"安装点位 {location} 已被占用")
                    break
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认导视":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "导视牌不存在"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        by_type: dict[str, int] = {}
        for r in rows:
            t = str(r.get("发光类型", ""))
            by_type[t] = by_type.get(t, 0) + 1
        base["by_light_type"] = by_type
        return base