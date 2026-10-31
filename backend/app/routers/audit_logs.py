from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.db import get_db
from app.models import AuditLog, User, RequestItem
from app.routers.auth import CurrentUser, get_current_user, require_roles
from app.schemas import AuditLogOut
from pydantic import BaseModel
from datetime import datetime

class AuditLogResponse(BaseModel):
    id: int
    item_name: str | None
    actor_role: str
    action: str
    note: str | None
    created_at: datetime

# owner and finance may view audit logs; all authenticated users satisfy the
# router-level dependency, role check is per-endpoint.
router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/api/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner", "finance")),
):
    results = db.execute(
        select(AuditLog, User.role, RequestItem.raw_name)
        .join(User, AuditLog.user_id == User.id)
        .join(RequestItem, AuditLog.request_item_id == RequestItem.id)
        .order_by(AuditLog.created_at.desc())
    ).all()
    
    return [
        AuditLogResponse(
            id=log.id,
            item_name=item_name,
            actor_role=role,
            action=log.action,
            note=log.note,
            created_at=log.created_at
        )
        for log, role, item_name in results
    ]
