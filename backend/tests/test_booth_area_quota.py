"""展位净面积核算与确认配额联动测试。

复现业务场景：
1. 撤回 10㎡ 展位后，场馆按净占用口径有 28㎡ 可供分配；
2. 两位策展人同时点确认：一笔尺寸刚从「待核对」更正为 18㎡，
   另一笔 15㎡ 在等回执，两笔都具备方案审核资格；
3. 场馆配额与展位确认关联后，从确认入口核查哪笔实际获得面积；
4. 用剩余面积再办 12㎡ 请求，并核对 10㎡ / 13㎡ 余量下的结果；
5. 尺寸无法解释的记录单列，不与撤回展位混算。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import exhibition, service_for
from app.store import store


VENUE_NAME = "D馆净面积测试厅"


class BoothNetAreaQuotaTestBase(unittest.TestCase):
    """每个用例独立搭建场景并在结束后还原全局仓库。"""

    def setUp(self):
        # 深拷贝现场，保证用例之间以及与其他测试文件互不污染
        import copy
        self._tables_backup = copy.deepcopy(store._tables)
        self._counters_backup = dict(store._id_counters)
        self._events_backup = list(store.event_log.entries)

        self.booth_service = service_for("booth")
        self.venue_id = self._add_venue(28)
        # T01：已确认的 10㎡ 展位，稍后撤回
        self.t01 = self._add_booth("BOOT-T01", "10", "已确认")
        self._add_design("BOOT-T01")
        # T02：尺寸待核对（无法解释），具备方案，稍后更正为 18㎡
        self.t02 = self._add_booth("BOOT-T02", "待核对", "待确认")
        self._add_design("BOOT-T02")
        # T03：15㎡ 展位，待确认等回执，具备方案
        self.t03 = self._add_booth("BOOT-T03", "15", "待确认")
        self._add_design("BOOT-T03")
        store.rebuild_indices()

    def tearDown(self):
        import copy
        store._tables = copy.deepcopy(self._tables_backup)
        store._id_counters = dict(self._counters_backup)
        store.event_log.entries = list(self._events_backup)
        store.rebuild_indices()

    def _add_venue(self, area):
        venue_id = store.next_id("venue")
        store.rows("venue").append({
            "id": venue_id, "status": "已确认", "pending": False, "abnormal": False,
            "场馆名称": VENUE_NAME, "可用面积": str(area), "层高限制": "6米",
            "地面承重": "2吨/㎡", "登记编号": f"VENU-T{venue_id}", "负责人": "测试策展",
            "生效版本": "v1.0", "备注说明": "净面积核算测试",
        })
        return venue_id

    def _add_booth(self, no, size, status):
        booth_id = store.next_id("booth")
        store.rows("booth").append({
            "id": booth_id, "status": status,
            "pending": status != "已撤回" and status != "已确认",
            "abnormal": False,
            "展位编号": no, "面积尺寸": size, "开口方向": "北",
            "所属区域": VENUE_NAME, "登记编号": f"BOOT-T{booth_id}",
            "负责人": "测试策展", "生效版本": "v1.0", "备注说明": no,
        })
        return booth_id

    def _add_design(self, booth_no):
        design_id = store.next_id("design")
        store.rows("design").append({
            "id": design_id, "status": "已确认", "pending": False, "abnormal": False,
            "设计风格": "测试风", "结构材料": "测试材料", "搭建高度": "3",
            "用电负荷": "10", "登记编号": f"DESI-T{design_id}", "负责人": "测试设计",
            "生效版本": "v1.0", "备注说明": booth_no,
        })

    def _capacity(self):
        return exhibition.check_venue_capacity(self.venue_id)

    def _confirm(self, booth_id):
        return self.booth_service.run_action(booth_id, "确认展位")


class TestWithdrawnAreaReleased(BoothNetAreaQuotaTestBase):
    """撤回展位让出的面积可重新分配，且不与待核对尺寸混算。"""

    def test_withdraw_releases_10sqm_leaving_28(self):
        # 撤回前：10㎡ 已确认占用，仅剩 18㎡
        before = self._capacity()["quota"]
        self.assertEqual(before["net_occupied_area"], 10.0)
        self.assertEqual(before["available_area"], 18.0)

        entry, message = self.booth_service.run_action(self.t01, "撤回记录")
        self.assertIsNotNone(entry, message)
        self.assertEqual(entry["status"], "已撤回")

        quota = self._capacity()["quota"]
        # 撤回后净占用归零，28㎡ 全部回到可分配池
        self.assertEqual(quota["net_occupied_area"], 0.0)
        self.assertEqual(quota["available_area"], 28.0)
        self.assertEqual(quota["remaining"], 28.0)
        # 撤回展位单列，不进确认合计
        self.assertEqual([b["booth_no"] for b in quota["withdrawn_booths"]], ["BOOT-T01"])
        self.assertEqual(quota["confirmed_booths"], [])

    def test_unverifiable_size_listed_separately_not_counted(self):
        # T02 尺寸为「待核对」：无法解释，单列且不占面积
        result = self._capacity()
        quota = result["quota"]
        unverifiable = quota["unverifiable_booths"]
        self.assertEqual(len(unverifiable), 1)
        self.assertEqual(unverifiable[0]["booth_no"], "BOOT-T02")
        self.assertEqual(unverifiable[0]["raw_size"], "待核对")
        # 净占用只来自已确认的 T01，待核对记录没有被按 0㎡ 之外的方式混入
        self.assertEqual(quota["net_occupied_area"], 10.0)
        self.assertTrue(any("无法解释" in u["reason"] for u in unverifiable))

    def test_unverifiable_booth_confirm_blocked_until_corrected(self):
        entry, message = self._confirm(self.t02)
        self.assertIsNone(entry, "尺寸无法解释时确认必须被拦截")
        self.assertIn("无法解释", message)

        # 策展人更正尺寸为 18㎡（先撤回 T01 腾出 28㎡）
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        entry, message = self._confirm(self.t02)
        self.assertIsNotNone(entry, f"更正后应可确认: {message}")
        self.assertEqual(entry["status"], "已确认")

    def test_create_entry_flags_unverifiable_as_abnormal(self):
        entry, errors = self.booth_service.create_entry({
            "展位编号": "BOOT-T99", "面积尺寸": "待核对",
            "开口方向": "南", "所属区域": VENUE_NAME,
        })
        self.assertIsNotNone(entry, errors)
        self.assertTrue(entry["abnormal"], "尺寸无法解释的新登记应单列标记异常")
        # 清理该行，避免影响后续断言
        store.rows("booth").remove(entry)
        store.rebuild_indices()


class TestConcurrentConfirmationQuota(BoothNetAreaQuotaTestBase):
    """两位策展人同时确认：先过配额门禁者获得面积，后者被拒。"""

    def _prepare_28_available(self):
        # 撤回 10㎡ 展位 → 28㎡ 可分配；T02 尺寸更正为 18㎡
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        store.rebuild_indices()

    def test_18sqm_wins_then_15sqm_rejected(self):
        self._prepare_28_available()
        self.assertEqual(self._capacity()["quota"]["available_area"], 28.0)

        # 第一笔：18㎡（刚从待核对更正），两笔都有方案审核资格
        entry_18, msg_18 = self._confirm(self.t02)
        self.assertIsNotNone(entry_18, msg_18)
        self.assertEqual(entry_18["status"], "已确认")

        # 第二笔：15㎡ 等回执，此时仅剩 10㎡
        entry_15, msg_15 = self._confirm(self.t03)
        self.assertIsNone(entry_15, "剩余 10㎡ 不足以确认 15㎡，必须拒绝")
        self.assertIn("15", msg_15)
        self.assertIn("10", msg_15)

        # 从确认入口核查：只有 T02 实际获得面积
        quota = self._capacity()["quota"]
        self.assertEqual([b["booth_no"] for b in quota["confirmed_booths"]], ["BOOT-T02"])
        self.assertEqual(quota["net_occupied_area"], 18.0)
        self.assertEqual(quota["available_area"], 10.0)
        self.assertEqual(store.find("booth", self.t03)["status"], "待确认")
        # 事件日志中只有 T02 的确认展位事件
        confirm_events = [
            e for e in store.event_log.for_module("booth")
            if e["action"] == "确认展位"
        ]
        self.assertEqual(len(confirm_events), 1)
        self.assertEqual(confirm_events[0]["entry_id"], self.t02)

    def test_reverse_order_15sqm_wins_then_18sqm_rejected(self):
        """反向顺序同样安全：先到先得，合计永远不突破上限。"""
        self._prepare_28_available()

        entry_15, msg_15 = self._confirm(self.t03)
        self.assertIsNotNone(entry_15, msg_15)
        entry_18, msg_18 = self._confirm(self.t02)
        self.assertIsNone(entry_18, "剩余 13㎡ 不足以确认 18㎡")
        self.assertIn("18", msg_18)
        self.assertIn("13", msg_18)

        quota = self._capacity()["quota"]
        self.assertEqual([b["booth_no"] for b in quota["confirmed_booths"]], ["BOOT-T03"])
        self.assertEqual(quota["net_occupied_area"], 15.0)
        self.assertEqual(quota["available_area"], 13.0)


class TestFollowUpRequestAtDifferentRemaining(BoothNetAreaQuotaTestBase):
    """用剩余面积再办 12㎡ 请求：10㎡ 余量拒、13㎡ 余量成；边界 10㎡ 请求可成。"""

    def test_12sqm_rejected_when_only_10_remaining(self):
        # 撤回 T01、确认 18㎡ 的 T02 → 剩余 10㎡
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        store.rebuild_indices()
        self._confirm(self.t02)
        self.assertEqual(self._capacity()["quota"]["available_area"], 10.0)

        t04 = self._add_booth("BOOT-T04", "12", "待确认")
        self._add_design("BOOT-T04")
        store.rebuild_indices()

        entry, message = self._confirm(t04)
        self.assertIsNone(entry, "12㎡ 请求在 10㎡ 余量下办不成")
        self.assertIn("12", message)
        self.assertEqual(store.find("booth", t04)["status"], "待确认")

    def test_exact_10sqm_approved_at_10_remaining_boundary(self):
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        store.rebuild_indices()
        self._confirm(self.t02)

        t04 = self._add_booth("BOOT-T04", "10", "待确认")
        self._add_design("BOOT-T04")
        store.rebuild_indices()

        entry, message = self._confirm(t04)
        self.assertIsNotNone(entry, f"恰好等于余量时应可办成: {message}")
        quota = self._capacity()["quota"]
        self.assertEqual(quota["available_area"], 0.0)
        self.assertTrue(self._capacity()["ok"], "用满但不超限仍为通过")

    def test_12sqm_approved_when_13_remaining(self):
        # 反向顺序：确认 15㎡ 的 T03 → 剩余 13㎡
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        store.rebuild_indices()
        self._confirm(self.t03)
        self.assertEqual(self._capacity()["quota"]["available_area"], 13.0)

        t04 = self._add_booth("BOOT-T04", "12", "待确认")
        self._add_design("BOOT-T04")
        store.rebuild_indices()

        entry, message = self._confirm(t04)
        self.assertIsNotNone(entry, f"12㎡ 在 13㎡ 余量下应能办成: {message}")
        self.assertEqual(store.find("booth", t04)["status"], "已确认")
        quota = self._capacity()["quota"]
        self.assertEqual(quota["net_occupied_area"], 27.0)
        self.assertEqual(quota["available_area"], 1.0)


class TestSnapshotsExposeNetConclusion(BoothNetAreaQuotaTestBase):
    """场馆规划向展位确认输出净占用口径的可用面积结论。"""

    def test_venue_snapshot_contains_area_conclusion(self):
        snapshot = service_for("venue").domain_snapshot()
        conclusion = next(
            c for c in snapshot["area_conclusions"] if c["venue_id"] == self.venue_id
        )
        self.assertEqual(conclusion["venue_area"], 28.0)
        self.assertEqual(conclusion["net_occupied_area"], 10.0)
        self.assertEqual(conclusion["available_area"], 18.0)
        # T02 尺寸无法解释，结论里带待改正计数
        self.assertEqual(conclusion["unverifiable_count"], 1)

    def test_booth_snapshot_lists_unverifiable_separately(self):
        snapshot = self.booth_service.domain_snapshot()
        nos = [u["booth_no"] for u in snapshot["unverifiable_booths"]]
        self.assertIn("BOOT-T02", nos)
        # 净占用只算已确认且可解释的展位：种子展位 600+400+300，
        # 加上本场景已确认的 T01 10㎡；待核对的 T02 不计入
        self.assertEqual(snapshot["net_occupied_area"], 1310.0)
        self.assertEqual(snapshot["total_confirmed_area"], 1310.0)

    def test_confirmed_total_never_exceeds_venue_cap(self):
        self.booth_service.run_action(self.t01, "撤回记录")
        store.find("booth", self.t02)["面积尺寸"] = "18㎡"
        store.rebuild_indices()
        self._confirm(self.t02)
        # 15㎡ 确认被拒后，场馆配额结论依然成立、未超限
        self._confirm(self.t03)
        result = self._capacity()
        self.assertTrue(result["ok"])
        self.assertLessEqual(result["quota"]["net_occupied_area"],
                             result["quota"]["venue_area"])
        # 综合配额视图同样保持通过
        summary = exhibition.quota_summary()
        venue_results = [q for q in summary["area_quotas"]
                         if q.get("venue_id") == self.venue_id]
        self.assertTrue(venue_results)
        self.assertTrue(venue_results[0]["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
