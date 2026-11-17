import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Receiver, OutboundPlan, Shipment, FieldEntry
from src.schemas.outbound import ReceiverInput, FaultInput, OutboundPlanInput
from src.middlewares.auth import current_user, admin_only
from src.services import outbound
from src.services.audit import record
from src.utils.serialization import receiver_dict, outbound_plan_dict, shipment_dict, field_entry_dict
router = APIRouter()
@router.get('/receivers')
def receivers(db=Depends(get_db), u=Depends(current_user)):
    return [receiver_dict(r) for r in db.scalars(select(Receiver).order_by(Receiver.id))]
@router.post('/receivers', status_code=201)
def create_receiver(data: ReceiverInput, db=Depends(get_db), u=Depends(admin_only)):
    r = Receiver(name=data.name, fault='none', created_at=time.time())
    db.add(r); db.flush()
    record(db, u.email, 'receiver.create', {'id': r.id, 'name': r.name}); db.commit()
    return receiver_dict(r)
@router.post('/receivers/{id}/fault')
def set_fault(id: int, data: FaultInput, db=Depends(get_db), u=Depends(admin_only)):
    r = db.get(Receiver, id)
    if not r:
        raise HTTPException(404, '接收端不存在')
    r.fault = data.fault
    record(db, u.email, 'receiver.fault', {'id': id, 'fault': data.fault}); db.commit()
    return receiver_dict(r)
@router.get('/outbound-plans')
def plans(db=Depends(get_db), u=Depends(current_user)):
    return [outbound_plan_dict(p) for p in db.scalars(select(OutboundPlan).order_by(OutboundPlan.id.desc()))]
@router.post('/outbound-plans', status_code=201)
def create_plan(data: OutboundPlanInput, db=Depends(get_db), u=Depends(admin_only)):
    p = outbound.create_plan(db, data)
    record(db, u.email, 'outbound.plan', {'id': p.id, 'receiver_id': p.receiver_id}); db.commit()
    return outbound_plan_dict(p)
@router.post('/outbound-plans/{id}/toggle')
def toggle_plan(id: int, db=Depends(get_db), u=Depends(admin_only)):
    p = db.get(OutboundPlan, id)
    if not p:
        raise HTTPException(404, '外送计划不存在')
    p.enabled = not p.enabled
    record(db, u.email, 'outbound.toggle', {'id': id, 'enabled': p.enabled}); db.commit()
    return outbound_plan_dict(p)
@router.post('/outbound-plans/{id}/fire', status_code=201)
def fire_now(id: int, db=Depends(get_db), u=Depends(admin_only)):
    p = db.get(OutboundPlan, id)
    if not p:
        raise HTTPException(404, '外送计划不存在')
    sh = outbound.fire_plan(db, p)
    if not sh:
        raise HTTPException(409, '分析结果未批准或接收端不存在，无法外送')
    p.next_run = time.time() + p.interval_seconds
    record(db, u.email, 'outbound.fire', {'plan': id, 'shipment': sh.id, 'delivery_no': sh.delivery_no})
    db.commit()
    return shipment_dict(sh)
@router.get('/shipments')
def shipments(db=Depends(get_db), u=Depends(current_user)):
    return [shipment_dict(s) for s in db.scalars(select(Shipment).order_by(Shipment.id.desc()).limit(200))]
@router.post('/shipments/{id}/reconcile')
def reconcile(id: int, db=Depends(get_db), u=Depends(admin_only)):
    sh = outbound.attempt(db, id, mode='check', actor=u.email)
    record(db, u.email, 'shipment.reconcile', {'id': id, 'status': sh.status}); db.commit()
    return shipment_dict(sh)
@router.post('/shipments/{id}/retry')
def retry(id: int, db=Depends(get_db), u=Depends(admin_only)):
    sh = outbound.attempt(db, id, mode='send', actor=u.email)
    record(db, u.email, 'shipment.retry', {'id': id, 'status': sh.status}); db.commit()
    return shipment_dict(sh)
@router.get('/field-ledger')
def field_ledger(db=Depends(get_db), u=Depends(current_user)):
    return [field_entry_dict(e) for e in db.scalars(select(FieldEntry).order_by(FieldEntry.id.desc()).limit(200))]
