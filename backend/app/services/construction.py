"""搭建进度领域服务：DAG拓扑管理、前置依赖推进、环检测。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class ConstructionService(BaseModuleService):
    MODULE = "construction"
    ENTITY = "进度节点"
    OPERATION_TERM = "更新进度"
    LIST_FIELDS = ["节点名称", "计划日期", "完成日期", "前置节点", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["节点名称", "计划日期", "前置节点"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"更新进度": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["change_order"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        node_name = str(values.get("节点名称", "")).strip()
        if not node_name:
            errors.append("节点名称不能为空")
        # 创建后检测环
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "更新进度":
            node = store.find(self.MODULE, entry_id)
            if node is None:
                return False, "进度节点不存在"
            result = exhibition.validate_dag_advance(entry_id)
            if not result["ok"]:
                return False, result["reason"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        cycle = exhibition.detect_cycle(rows)
        order = exhibition.build_dag_order(rows) if cycle is None else []
        base["dag_cycle"] = cycle
        base["dag_order"] = order
        base["dag_valid"] = cycle is None
        return base