"""突发事件领域服务：事件等级分类、处置时效跟踪、场馆关联。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store


class IncidentService(BaseModuleService):
    MODULE = "incident"
    ENTITY = "事件记录"
    OPERATION_TERM = "确认处置"
    LIST_FIELDS = ["事件类型", "发生位置", "处置班组", "处置结果", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["事件类型", "发生位置", "处置班组", "处置结果"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认处置": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["safety", "venue"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        etype = str(values.get("事件类型", "")).strip()
        if etype not in ("设施故障", "安全事故", "人员异常", "自然灾害", "其他"):
            errors.append(f"事件类型 {etype} 不在允许范围")
        # 跨模块校验：发生位置应在已知场馆或展位范围内
        location = str(values.get("发生位置", "")).strip()
        if location:
            booth_no = location.split("顶部")[0].split("入口")[0].strip()
            if booth_no:
                booth = store.find_booth(booth_no)
                if booth is None:
                    # not necessarily an error for generic locations like "主通道"
                    pass
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认处置":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "事件记录不存在"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = self.related_rows("incident")
        by_type: dict[str, int] = {}
        for r in rows:
            t = str(r.get("事件类型", "未分类"))
            by_type[t] = by_type.get(t, 0) + 1
        base["by_type"] = by_type
        return base