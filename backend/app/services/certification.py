"""认证认可业务规则：资质台账与资质覆盖视图共用同一套筛选、状态与排序口径。

状态口径：已注销的人工标记优先；其余一律按「有效期至」相对当前日期推导——
已经过期排在最前，其次是 90 天内到期的临期证书，再到有效证书。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "certification"
CATALOG_MODULE = "cert_scope_catalog"
COVERAGE_MODULE = "cert_coverage_item"
REQUIRED_FIELDS = ["认定编号", "认定类型", "发证机构"]
# 已过期、临期固定排在最前面；同组内按有效期至升序，越早越靠前。
STATUS_ORDER = ["已过期", "临期", "有效", "已注销"]
STATUS_RANK = {status: index for index, status in enumerate(STATUS_ORDER)}
NEAR_EXPIRE_DAYS = 90
VALID_YEARS = 6
ACTION_RULES = {"续证申请": "有效", "登记过期": "已过期", "注销证书": "已注销"}
# 触发人工状态的动作：登记过期、注销证书不再按日期推导。
_OVERRIDE_ACTIONS = {"登记过期": "已过期", "注销证书": "已注销"}
NEGATIVE_ACTIONS = ["登记过期", "注销证书"]

_FAR_FUTURE = date(9999, 12, 31)


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _split_scopes(value: Any) -> list[str]:
    """认定范围按顿号/逗号拆成多个范围项，空项丢掉、重复项只保留一次。"""
    text = str(value or "").strip()
    if not text:
        return []
    result: list[str] = []
    for piece in text.replace(",", "、").replace("，", "、").split("、"):
        scope = piece.strip()
        if scope and scope not in result:
            result.append(scope)
    return result


def _expiry_of(row: dict[str, Any]) -> date:
    parsed = _parse_date(row.get("有效期至"))
    return parsed if parsed is not None else _FAR_FUTURE


def derive_status(row: dict[str, Any], *, today: date | None = None) -> str:
    """按有效期至推导认定状态；已注销等人工标记优先级最高。"""
    override = str(row.get("status_override") or "").strip()
    if override in STATUS_RANK:
        return override
    expiry = _parse_date(row.get("有效期至"))
    if expiry is None:
        return "有效"
    current = today or date.today()
    if expiry < current:
        return "已过期"
    if expiry <= current + timedelta(days=NEAR_EXPIRE_DAYS):
        return "临期"
    return "有效"


class CertificationService:
    # ---- 台账与覆盖视图共用的筛选/排序口径 ---------------------------------

    def _query_rows(
        self,
        *,
        keyword: str | None = None,
        cert_type: str | None = None,
        status: str | None = None,
        today: date | None = None,
    ) -> list[dict[str, Any]]:
        rows = [self._decorate(row, today=today) for row in store.rows(MODULE)]
        if cert_type:
            rows = [row for row in rows if row.get("认定类型") == cert_type]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("认定编号", ""))
                or key in str(row.get("发证机构", ""))
                or key in str(row.get("认定范围", ""))
            ]
        rows.sort(key=lambda row: (STATUS_RANK[str(row["status"])], _expiry_of(row), str(row.get("认定编号", ""))))
        return rows

    def _decorate(self, row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
        """给台账行补一份按日期推导的状态，保证列表、覆盖视图、导出口径一致。"""
        status = derive_status(row, today=today)
        row["status"] = status
        row["认定状态"] = status
        row["pending"] = status != "已注销"
        row["abnormal"] = status in ("临期", "已过期")
        return row

    # ---- 资质台账 -----------------------------------------------------------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        cert_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._query_rows(keyword=keyword, cert_type=cert_type, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._decorate(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("认定范围", "获证日期", "有效期至", "证书编号"):
            if values.get(field) is not None:
                entry[field] = values.get(field)
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._decorate(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"资质认定 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于认证认可可执行范围"
        if action == "续证申请":
            entry["有效期至"] = self._renew_until(entry)
            entry.pop("status_override", None)
        elif action in _OVERRIDE_ACTIONS:
            entry["status_override"] = _OVERRIDE_ACTIONS[action]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._decorate(entry), f"资质认定已{action}"

    @staticmethod
    def _renew_until(row: dict[str, Any]) -> str:
        """续证后有效期顺延一个认定周期（6 年）；原有效期读不出来就从今天起算。"""
        base = _parse_date(row.get("有效期至")) or date.today()
        if base <= date.today():
            base = date.today()
        year = base.year + VALID_YEARS
        try:
            renewed = base.replace(year=year)
        except ValueError:
            # 2 月 29 日顺到非闰年时落到当月最后一天。
            renewed = date(year, 2, 28)
        return renewed.isoformat()

    # ---- 资质覆盖视图 -------------------------------------------------------

    def list_types(self) -> list[dict[str, str]]:
        seen: list[str] = []
        for row in store.rows(MODULE):
            cert_type = str(row.get("认定类型") or "").strip()
            if cert_type and cert_type not in seen:
                seen.append(cert_type)
        return [{"认定类型": cert_type} for cert_type in seen]

    def list_coverage(
        self,
        *,
        keyword: str | None = None,
        cert_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """覆盖清单与台账同源同序，只额外给出每个范围可开展的项目数量。"""
        result = []
        for row in self._query_rows(keyword=keyword, cert_type=cert_type, status=status):
            item = dict(row)
            item["scopes"] = [
                {
                    "认定范围": scope,
                    "可开展项目数": self._covered_keys(row, scope).__len__(),
                }
                for scope in _split_scopes(row.get("认定范围"))
            ]
            result.append(item)
        return result

    def scope_detail(self, entry_id: int, scope_name: str) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        entry = self._decorate(entry)
        scopes = _split_scopes(entry.get("认定范围"))
        scope = next((item for item in scopes if item == scope_name), None)
        if scope is None:
            return None
        covered = self._covered_keys(entry, scope)
        items: list[dict[str, Any]] = []
        for catalog_row in store.rows(CATALOG_MODULE):
            if catalog_row.get("认定范围") != scope:
                continue
            name = str(catalog_row.get("检测项目") or "")
            items.append({
                "检测项目": name,
                "检测标准": catalog_row.get("检测标准"),
                "覆盖状态": "可开展" if name in covered else "暂无覆盖",
            })
        covered_names = {item["检测项目"] for item in items if item["覆盖状态"] == "可开展"}
        # 附表里登记了、但项目目录还没维护的项目也带出来，并说明目录口径缺失。
        for name in sorted(covered - covered_names):
            items.append({"检测项目": name, "检测标准": None, "覆盖状态": "可开展（目录未登记）"})
        return {
            "id": entry["id"],
            "认定编号": entry.get("认定编号"),
            "认定类型": entry.get("认定类型"),
            "认定状态": entry.get("认定状态"),
            "发证机构": entry.get("发证机构"),
            "获证日期": entry.get("获证日期"),
            "有效期至": entry.get("有效期至"),
            "认定范围": scope,
            "covered_count": sum(1 for item in items if item["覆盖状态"] == "可开展"),
            "uncovered_count": sum(1 for item in items if item["覆盖状态"] == "暂无覆盖"),
            "items": items,
        }

    @staticmethod
    def _covered_keys(row: dict[str, Any], scope: str) -> set[str]:
        cert_no = str(row.get("认定编号") or "")
        return {
            str(item.get("检测项目") or "")
            for item in store.rows(COVERAGE_MODULE)
            if str(item.get("认定编号") or "") == cert_no
            and str(item.get("认定范围") or "") == scope
        }
