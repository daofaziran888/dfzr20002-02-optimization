"""影音布置领域服务：设备安装位置合规检查、信号线路连通性校验、展位关联。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store


class AudioVisualService(BaseModuleService):
    MODULE = "audio_visual"
    ENTITY = "影音设备"
    OPERATION_TERM = "调试设备"
    LIST_FIELDS = ["设备型号", "安装位置", "信号线路", "调试试音", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["设备型号", "安装位置", "信号线路"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"调试设备": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["electrical", "booth"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        model = str(values.get("设备型号", "")).strip()
        if not model:
            errors.append("设备型号不能为空")
        # 跨模块校验：影音设备备注说明应对应有效展位
        remark = str(values.get("备注说明", "")).strip()
        if remark:
            booth_no = ""
            for part in remark.split():
                if part.startswith("BOOT-"):
                    booth_no = part.strip()
                    break
            if booth_no:
                booth = store.find_booth(booth_no)
                if booth is None:
                    errors.append(f"展位 {booth_no} 不存在，请先登记展位")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "调试设备":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "影音设备不存在"
            # 检查关联展位用电已核验
            remark = str(entry.get("备注说明", ""))
            booth_no = ""
            for part in remark.split():
                if part.startswith("BOOT-"):
                    booth_no = part.strip()
                    break
            if booth_no:
                circuits = store.booth_electrical(booth_no)
                confirmed = [c for c in circuits if c.get("status") == "已确认"]
                if not confirmed:
                    return False, f"展位 {booth_no} 用电回路尚未核验，影音设备不可调试"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        booth_linked = sum(1 for r in rows if "BOOT-" in str(r.get("备注说明", "")))
        base["booth_linked_count"] = booth_linked
        return base