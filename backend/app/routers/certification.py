"""认证认可接口：资质台账与资质覆盖视图共用一套筛选、状态与排序口径。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.certification import STATUS_ORDER, CertificationService

router = APIRouter(prefix="/api/certification", tags=["认证认可"])

service = CertificationService()

LIST_FIELDS = ["认定编号", "认定类型", "发证机构", "认定范围", "获证日期", "有效期至", "证书编号", "认定状态"]
STATUSES = STATUS_ORDER


def _resolve_filters(
    keyword: str | None,
    cert_type: str | None,
    status: str | None,
) -> tuple[str | None, str | None, str | None]:
    if status and status not in STATUS_ORDER:
        raise HTTPException(status_code=400, detail=f"认定状态只能是：{'、'.join(STATUS_ORDER)}")
    return keyword, cert_type, status


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按认定编号、发证机构或认定范围检索"),
    cert_type: str | None = Query(default=None, alias="type", description="按认定类型筛选"),
    status: str | None = Query(default=None, description="已过期、临期、有效、已注销"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按认定编号、认定类型与状态过滤资质台账；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    keyword, cert_type, status = _resolve_filters(keyword, cert_type, status)
    items, total = service.list_entries(
        keyword=keyword, cert_type=cert_type, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/types")
def list_types() -> dict[str, Any]:
    """资质台账里出现过的认定类型，供视图切换与筛选项使用。"""
    types = service.list_types()
    return {"total": len(types), "items": types}


@router.get("/coverage")
def list_coverage(
    keyword: str | None = Query(default=None, description="按认定编号、发证机构或认定范围检索"),
    cert_type: str | None = Query(default=None, alias="type", description="按认定类型筛选"),
    status: str | None = Query(default=None, description="已过期、临期、有效、已注销"),
) -> dict[str, Any]:
    """资质覆盖视图：与资质台账同源同序，额外带出每个认定范围可开展的项目数。"""
    keyword, cert_type, status = _resolve_filters(keyword, cert_type, status)
    items = service.list_coverage(keyword=keyword, cert_type=cert_type, status=status)
    return {"module": "certification", "total": len(items), "items": items}


@router.get("/coverage/{entry_id}")
def get_coverage_scope(
    entry_id: int,
    scope: str = Query(..., description="认定范围名称"),
) -> dict[str, Any]:
    """某个认定范围内可开展的检测项目清单；目录里未覆盖的项目标记为暂无覆盖。"""
    detail = service.scope_detail(entry_id, scope)
    if detail is None:
        raise HTTPException(status_code=404, detail="该资质认定下未找到此认定范围")
    return detail


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None),
    cert_type: str | None = Query(default=None, alias="type"),
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    """导出资质清单：按当前资质覆盖视图的筛选条件与排列顺序返回全量数据。"""
    keyword, cert_type, status = _resolve_filters(keyword, cert_type, status)
    items = service.list_coverage(keyword=keyword, cert_type=cert_type, status=status)
    return {"module": "certification", "total": len(items), "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条资质认定明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"资质认定 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条资质认定，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="资质认定已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条资质认定执行续证申请、登记过期、注销证书；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
