"""灯光编排领域服务：灯位坐标校验、色温范围与光束角度合规检查、展位关联。"""
from __future__ import annotations
from typing import Any
from app.services.base import BaseModuleService
from app.store import store


class LightingService(BaseModuleService):
    MODULE = "lighting"
    ENTITY = "灯光方案"
    OPERATION_TERM = "确认灯光"
    LIST_FIELDS = ["灯位坐标", "色温设定", "光束角度", "控制通道", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["灯位坐标", "色温设定", "光束角度"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认灯光": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["electrical", "booth"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        temp = str(values.get("色温设定", "")).strip()
        if temp and not temp.endswith("K"):
            try:
                k = int(temp)
                if k < 2700 or k > 6500:
                    errors.append(f"色温 {k}K 不在 2700-6500K 范围")
            except ValueError:
                errors.append(f"色温 {temp} 格式不正确")
        angle = str(values.get("光束角度", "")).strip()
        if angle:
            try:
                a = int(angle.replace("°", ""))
                if a <= 0 or a > 120:
                    errors.append(f"光束角度 {a}° 不在 1-120° 范围")
            except ValueError:
                errors.append(f"光束角度 {angle} 格式不正确")
        # 跨模块校验：灯光方案备注说明应对应有效展位
        remark = str(values.get("备注说明", "")).strip()
        if remark:
            booth_no = remark.split("主照明")[0].split("重点照明")[0].strip()
            if booth_no and booth_no.startswith("BOOT-"):
                booth = store.find_booth(booth_no)
                if booth is None:
                    errors.append(f"展位 {booth_no} 不存在，请先登记展位")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认灯光":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "灯光方案不存在"
            # 检查关联展位的用电是否已核验
            remark = str(entry.get("备注说明", ""))
            booth_no = remark.split("主照明")[0].split("重点照明")[0].strip()
            if booth_no and booth_no.startswith("BOOT-"):
                circuits = store.booth_electrical(booth_no)
                confirmed_circuits = [c for c in circuits if c.get("status") == "已确认"]
                if not confirmed_circuits:
                    return False, f"展位 {booth_no} 用电回路尚未核验，灯光方案不可确认"
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        booth_linked = sum(
            1 for r in rows if "BOOT-" in str(r.get("备注说明", ""))
        )
        base["booth_linked_count"] = booth_linked
        return base