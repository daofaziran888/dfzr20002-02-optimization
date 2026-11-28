"""用电配置领域服务：功率校验、展位负荷比对、断路器型号合规检查。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class ElectricalService(BaseModuleService):
    MODULE = "electrical"
    ENTITY = "用电回路"
    OPERATION_TERM = "核验用电"
    LIST_FIELDS = ["回路编号", "额定功率", "所属展位", "断路器型号", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["回路编号", "额定功率", "所属展位"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"核验用电": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["booth", "design"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        booth_no = str(values.get("所属展位", "")).strip()
        if booth_no:
            booth = store.find_booth(booth_no)
            if booth is None:
                errors.append(f"所属展位 {booth_no} 不存在，请先登记展位")
        try:
            power = float(str(values.get("额定功率", "0")).replace("kW", "").replace("W", "").strip())
            if power <= 0:
                errors.append("额定功率必须大于0")
        except (ValueError, AttributeError):
            errors.append("额定功率格式不正确")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "核验用电":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "用电回路不存在"
            booth_no = str(entry.get("所属展位", ""))
            if booth_no:
                result = exhibition.check_electrical_quota(booth_no)
                if not result["ok"]:
                    return False, result["reason"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        total_power = 0.0
        for c in confirmed:
            try:
                total_power += float(str(c.get("额定功率", "0")).replace("kW", "").replace("W", "").strip())
            except (ValueError, AttributeError):
                pass
        base["total_circuit_power"] = total_power
        return base