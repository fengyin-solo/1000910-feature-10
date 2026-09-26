"""认证认可接口：维护资质认定，覆盖续证申请、登记过期、注销证书等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.certification import CertificationService

router = APIRouter(prefix="/api/certification", tags=["认证认可"])

service = CertificationService()

LIST_FIELDS = ["认定编号", "认定类型", "发证机构", "认定范围", "获证日期", "有效期至", "证书编号", "认定状态"]
STATUSES = ["有效", "临期", "已过期", "已注销"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按认定编号检索"),
    status: str | None = Query(default=None, description="有效、临期、已过期、已注销"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按认定编号与状态过滤认证认可列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/coverage")
def coverage_view(
    cert_type: str | None = Query(default=None, description="按认定类型过滤，切换后排列顺序跟着变"),
    keyword: str | None = Query(default=None, description="按认定编号检索"),
    status: str | None = Query(default=None, description="有效、临期、已过期、已注销"),
) -> dict[str, Any]:
    """资质覆盖视图：与台账同一口径，临期与已过期的排在前面，并给出仍暂无覆盖的项目。"""
    items, total = service.list_coverage(keyword=keyword, status=status, cert_type=cert_type)
    return {
        "items": items,
        "total": total,
        "types": service.cert_types(),
        "uncovered_projects": service.uncovered_projects(),
    }


@router.get("/coverage/{entry_id}")
def coverage_detail(entry_id: int) -> dict[str, Any]:
    """单个认定范围的检测项目清单；没覆盖到的项目以 covered=false 返回，由页面标注暂无覆盖。"""
    detail = service.coverage_detail(entry_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"资质认定 {entry_id} 不存在或已归档")
    return detail


@router.get("/export")
def export_entries(
    view: str = Query(default="ledger", description="ledger 按台账登记顺序，coverage 按覆盖视图顺序"),
    cert_type: str | None = Query(default=None, description="按认定类型过滤"),
    keyword: str | None = Query(default=None, description="按认定编号检索"),
    status: str | None = Query(default=None, description="有效、临期、已过期、已注销"),
) -> dict[str, Any]:
    """导出资质清单：按当前视图的排列顺序给出，覆盖视图带认定类型筛选。"""
    if view == "coverage":
        items, total = service.list_coverage(keyword=keyword, status=status, cert_type=cert_type)
        return {"module": "certification", "view": "coverage", "total": total, "items": items}
    items, total = service.list_entries(keyword=keyword, status=status, page=1, size=10000)
    return {"module": "certification", "view": "ledger", "total": total, "items": items}


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
