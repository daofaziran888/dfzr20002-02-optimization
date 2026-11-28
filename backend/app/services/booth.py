"""展位编排领域服务：分配校验、净面积核算、展位状态联动各模块。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class BoothService(BaseModuleService):
    MODULE = "booth"
    ENTITY = "展位"
    OPERATION_TERM = "确认展位"
    LIST_FIELDS = ["展位编号", "面积尺寸", "开口方向", "所属区域", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["展位编号", "面积尺寸", "开口方向", "所属区域"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认展位": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["electrical", "design", "safety", "checklist", "handover"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        booth_no = str(values.get("展位编号", "")).strip()
        if not booth_no:
            errors.append("展位编号不能为空")
        else:
            existing = store.find_booth(booth_no)
            if existing:
                errors.append(f"展位编号 {booth_no} 已存在")
        return errors

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry, errors = super().create_entry(values)
        if entry is None:
            return entry, errors
        # 尺寸无法解释的记录允许登记，但单列标记为异常，供策展人改正；
        # 它不会被计入场馆净占用面积，也无法通过确认门禁。
        if exhibition.parse_area(entry.get("面积尺寸")) is None:
            entry["abnormal"] = True
        return entry, errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认展位":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "展位不存在"
            booth_no = str(entry.get("展位编号", ""))
            # 检查是否有设计方案（方案审核资格）
            designs = store.rows("design")
            has_design = any(str(d.get("备注说明", "")) == booth_no for d in designs)
            if not has_design:
                return False, f"展位 {booth_no} 需要先完成方案设计"
            # 确认动作与场馆面积配额联动：按净占用口径试算，防止超额确认
            quota_result = exhibition.check_booth_confirm_quota(entry_id)
            if not quota_result["ok"]:
                return False, quota_result["reason"]
        return True, ""

    def domain_snapshot(self, _visited: frozenset[str] | None = None) -> dict[str, Any]:
        base = super().domain_snapshot(_visited=_visited)
        rows = store.rows(self.MODULE)
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        base["confirmed_booths"] = [r.get("展位编号") for r in confirmed]
        # 净占用面积：只合计已确认且尺寸可解释的展位
        total_area = 0.0
        unverifiable: list[dict[str, Any]] = []
        for booth in rows:
            area = exhibition.parse_area(booth.get("面积尺寸"))
            if area is None:
                unverifiable.append({
                    "booth_id": booth.get("id"),
                    "booth_no": booth.get("展位编号"),
                    "raw_size": booth.get("面积尺寸", ""),
                    "status": booth.get("status", ""),
                })
            elif booth.get("status") == "已确认":
                total_area += area
        base["total_confirmed_area"] = total_area
        base["net_occupied_area"] = total_area
        # 尺寸无法解释的记录单列，不混进面积合计
        base["unverifiable_booths"] = unverifiable
        base["unverifiable_count"] = len(unverifiable)
        return base
