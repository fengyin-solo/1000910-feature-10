"""认证认可业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "certification"
TASK_MODULE = "task"
REQUIRED_FIELDS = ["认定编号", "认定类型", "发证机构"]
STATUS_ORDER = ["有效", "临期", "已过期", "已注销"]
ACTION_RULES = {"续证申请": "有效", "登记过期": "已过期", "注销证书": "已注销"}
NEGATIVE_ACTIONS = []

# 覆盖视图排序：临期与已过期的单独排在前面，其余保持台账登记顺序
URGENCY_ORDER = {"已过期": 0, "临期": 1}
# 仍具备检测开展效力的状态；已过期、已注销的资质不再计入项目覆盖
ACTIVE_STATUSES = {"有效", "临期"}


class CertificationService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._filter_rows(keyword=keyword, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"资质认定 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于认证认可可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"资质认定已{action}"

    def list_coverage(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        cert_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """资质覆盖视图：与台账同一过滤口径，临期与已过期的排在前面。"""
        rows = self._filter_rows(keyword=keyword, status=status, cert_type=cert_type)
        ordered = sorted(
            rows,
            key=lambda row: (URGENCY_ORDER.get(str(row.get("status")), len(URGENCY_ORDER)), int(row.get("id", 0))),
        )
        items = [self._coverage_item(row) for row in ordered]
        return items, len(items)

    def coverage_detail(self, entry_id: int) -> dict[str, Any] | None:
        """单个认定范围的项目清单：覆盖的可开展，没覆盖到的标注暂无覆盖。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        covered = {str(project) for project in entry.get("覆盖项目", [])}
        projects = [
            {"name": name, "covered": name in covered}
            for name in self._project_catalog()
        ]
        return {
            "entry": self._coverage_item(entry),
            "active": entry.get("status") in ACTIVE_STATUSES,
            "projects": projects,
            "covered_count": sum(1 for project in projects if project["covered"]),
            "uncovered_count": sum(1 for project in projects if not project["covered"]),
        }

    def uncovered_projects(self) -> list[str]:
        """实验室维度仍暂无覆盖的项目：没有任何有效或临期资质登记过它们。"""
        covered: set[str] = set()
        for row in store.rows(MODULE):
            if row.get("status") in ACTIVE_STATUSES:
                covered.update(str(project) for project in row.get("覆盖项目", []))
        return [name for name in self._project_catalog() if name not in covered]

    def cert_types(self) -> list[str]:
        """当前台账里出现过的认定类型，按登记顺序去重，供视图切换。"""
        types: list[str] = []
        for row in store.rows(MODULE):
            value = str(row.get("认定类型") or "").strip()
            if value and value not in types:
                types.append(value)
        return types

    def _filter_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        cert_type: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("认定编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if cert_type:
            rows = [row for row in rows if row.get("认定类型") == cert_type]
        return rows

    def _coverage_item(self, row: dict[str, Any]) -> dict[str, Any]:
        projects = [str(project) for project in row.get("覆盖项目", [])]
        return {
            "id": row.get("id"),
            "认定编号": row.get("认定编号"),
            "认定类型": row.get("认定类型"),
            "认定范围": row.get("认定范围"),
            "发证机构": row.get("发证机构"),
            "获证日期": row.get("获证日期"),
            "有效期至": row.get("有效期至"),
            "认定状态": row.get("status"),
            "覆盖项目": projects,
            "覆盖项目数": len(projects),
        }

    def _project_catalog(self) -> list[str]:
        """检测项目目录：资质登记过的项目加上检测任务里出现过的项目，去重保序。"""
        catalog: list[str] = []
        for row in store.rows(MODULE):
            for project in row.get("覆盖项目", []):
                name = str(project).strip()
                if name and name not in catalog:
                    catalog.append(name)
        for row in store.rows(TASK_MODULE):
            name = str(row.get("检测项目") or "").strip()
            if name and name not in catalog:
                catalog.append(name)
        return catalog
