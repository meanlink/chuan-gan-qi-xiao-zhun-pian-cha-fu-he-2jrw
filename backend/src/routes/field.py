"""本地模拟的现场系统接收端。

这是一个独立的模拟对端：只通过 /field-api 暴露入账与台账查询，
发送方（worker 或页面操作）以 HTTP 调用，不直接读写给台账表。
fault 由接收端配置驱动，用于在本地模拟丢回执、异内容入账与不可用。
"""
import time, json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from src.config.database import get_db
from src.models import Receiver, FieldEntry
from src.utils.serialization import checksum, field_entry_dict
router = APIRouter(prefix='/field-api')
class ReceiveInput(BaseModel):
    receiver_id: int
    delivery_no: str = Field(min_length=4, max_length=40)
    fingerprint: str = Field(min_length=64, max_length=64)
    payload: dict
def _corrupt(payload):
    p = json.loads(json.dumps(payload, ensure_ascii=False))
    result = p.get('result')
    if isinstance(result, dict):
        result['summary'] = str(result.get('summary', '')) + '（现场入账内容被篡改）'
    p['tampered_in_field'] = True
    return p
@router.post('/receive')
def receive(data: ReceiveInput, db=Depends(get_db)):
    receiver = db.get(Receiver, data.receiver_id)
    if not receiver:
        raise HTTPException(404, '接收端不存在')
    if receiver.fault == 'unavailable':
        raise HTTPException(503, '现场系统暂不可用（模拟），本场未入账')
    now = time.time()
    entry = db.scalar(select(FieldEntry).where(FieldEntry.receiver_id == receiver.id,
                                               FieldEntry.delivery_no == data.delivery_no))
    if entry:
        # 同一送达编号幂等：原号重试不重复入账，只记录接收次数
        entry.times += 1
        entry.last_receive_at = now
    else:
        payload, fingerprint = data.payload, data.fingerprint
        if receiver.fault == 'tamper':
            payload = _corrupt(data.payload)
            fingerprint = checksum(payload)
        entry = FieldEntry(receiver_id=receiver.id, delivery_no=data.delivery_no,
                           fingerprint=fingerprint, payload=payload, times=1,
                           recorded_at=now, last_receive_at=now)
        db.add(entry)
    db.commit()
    db.refresh(entry)
    if receiver.fault == 'lose_receipt':
        # 已入账，但回执在传输中丢失：发送方看到的是失败
        raise HTTPException(503, '回执在传输中丢失（模拟），对方实际已入账')
    return field_entry_dict(entry)
@router.get('/ledger/{delivery_no}')
def ledger_entry(delivery_no: str, receiver_id: int, db=Depends(get_db)):
    entry = db.scalar(select(FieldEntry).where(FieldEntry.receiver_id == receiver_id,
                                               FieldEntry.delivery_no == delivery_no))
    if not entry:
        raise HTTPException(404, '未查到该送达编号')
    return field_entry_dict(entry)
