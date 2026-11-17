"""外送计划与对账闭环。

状态机：待发 pending → 发送中 sending → 成功 success（终态）
                          ├─ 回执丢失/异常 → 待对账 reconciling
                          └─ 中断超时 → 恢复为待对账
        待对账 → 对账：同编号同内容 → 成功；异内容 → 冲突（隔离，终态）；未查到 → 原号重试

并发与恢复约定：
- 认领（claim）是原子 UPDATE，多进程同时接管只有一方成功；
- 每次执行携带 attempt_token，状态落库必须匹配 token 且来源状态合法，
  旧执行的晚回执因此无法覆盖新状态；
- 终态（成功/冲突）不接受任何迁移；
- 接收端按送达编号幂等入账，原号重试不会重复入账。
"""
import time, json, uuid, logging, urllib.request, urllib.error
from sqlalchemy import select, update, func
from fastapi import HTTPException
from src.config.database import Session
from src.config.settings import FIELD_SYSTEM_URL, OUTBOUND_RETRY_SECONDS, OUTBOUND_STALE_SECONDS
from src.models import Job, Receiver, OutboundPlan, Shipment
from src.services.audit import record
from src.utils.serialization import checksum

TERMINAL = ('success', 'conflict')
UNRESOLVED = ('pending', 'sending', 'reconciling')
HTTP_TIMEOUT = 5

def create_plan(db, data):
    j = db.get(Job, data.job_id)
    if not j or j.status != 'completed' or not j.approved:
        raise HTTPException(409, '请先选择已完成且获批准的分析结果')
    if not db.get(Receiver, data.receiver_id):
        raise HTTPException(404, '接收端不存在')
    p = OutboundPlan(name=data.name, job_id=j.id, receiver_id=data.receiver_id,
                     interval_seconds=data.interval_seconds,
                     next_run=time.time() + data.delay_seconds, enabled=True, created_at=time.time())
    db.add(p); db.flush()
    return p

def freeze_payload(job):
    """冻结批准结果快照；不含易变字段，同一批准结果各场内容指纹一致。"""
    return {'job_id': job.id, 'job_name': job.name, 'params': job.params, 'result': job.result}

def fire_plan(db, plan):
    """产生一场外送：冻结内容与送达编号。调用方负责提交事务。"""
    j = db.get(Job, plan.job_id)
    if not j or not j.approved:
        return None
    receiver = db.scalar(select(Receiver).where(Receiver.id == plan.receiver_id).with_for_update())
    if not receiver:
        return None
    seq = (db.scalar(select(func.max(Shipment.seq)).where(Shipment.receiver_id == receiver.id)) or 0) + 1
    payload = freeze_payload(j)
    now = time.time()
    sh = Shipment(plan_id=plan.id, receiver_id=receiver.id, seq=seq,
                  delivery_no='DLV-%02d-%06d' % (receiver.id, seq),
                  payload=payload, fingerprint=checksum(payload), status='pending',
                  attempts=0, attempt_token='', next_attempt_at=0, last_error='',
                  created_at=now, updated_at=now)
    db.add(sh); db.flush()
    return sh

def fire_due(db):
    """到期的启用计划各产生一场。先原子推进 next_run，崩溃则整场回滚可重放。"""
    now = time.time()
    due = list(db.execute(select(OutboundPlan.id, OutboundPlan.interval_seconds)
                          .where(OutboundPlan.enabled == True, OutboundPlan.next_run <= now)))
    for pid, interval in due:
        claimed = db.execute(update(OutboundPlan)
                             .where(OutboundPlan.id == pid, OutboundPlan.next_run <= now)
                             .values(next_run=time.time() + interval)).rowcount
        if claimed != 1:
            continue  # 其他进程已接管该计划的本次触发
        plan = db.get(OutboundPlan, pid)
        if plan:
            fire_plan(db, plan)
    db.commit()

def sweep_stale(db):
    """发送中断恢复：占用超时的发送中场次恢复为待对账，等待对账或重试。"""
    cutoff = time.time() - OUTBOUND_STALE_SECONDS
    res = db.execute(update(Shipment)
                     .where(Shipment.status == 'sending', Shipment.claimed_at < cutoff)
                     .values(status='reconciling', last_error='发送中断，已恢复为待对账',
                             next_attempt_at=0, updated_at=time.time()))
    db.commit()
    return res.rowcount

def head_unresolved(db, receiver_id):
    """同一接收方按场次顺序处理：返回最前的未决场次。"""
    return db.scalar(select(Shipment).where(Shipment.receiver_id == receiver_id,
                                            Shipment.status.in_(UNRESOLVED))
                     .order_by(Shipment.seq).limit(1))

def _claim(db, shipment_id, from_status, token):
    res = db.execute(update(Shipment)
                     .where(Shipment.id == shipment_id, Shipment.status == from_status)
                     .values(status='sending', attempt_token=token, claimed_at=time.time(),
                             attempts=Shipment.attempts + 1, updated_at=time.time()))
    db.commit()
    return res.rowcount == 1

def _settle(db, shipment_id, token, **values):
    """仅当前 token 的执行可迁移状态，且不允许覆盖终态；返回是否生效。"""
    values['updated_at'] = time.time()
    res = db.execute(update(Shipment)
                     .where(Shipment.id == shipment_id, Shipment.attempt_token == token,
                            Shipment.status.in_(('sending', 'reconciling')))
                     .values(**values))
    db.commit()
    return res.rowcount == 1

def _reload(db, shipment_id):
    db.expire_all()
    return db.get(Shipment, shipment_id)

def _brief(exc):
    text = str(exc) or exc.__class__.__name__
    return text[:120]

def _post_receive(sh):
    body = json.dumps({'receiver_id': sh.receiver_id, 'delivery_no': sh.delivery_no,
                       'fingerprint': sh.fingerprint, 'payload': sh.payload},
                      ensure_ascii=False, allow_nan=False).encode('utf-8')
    req = urllib.request.Request(FIELD_SYSTEM_URL + '/receive', data=body,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))

def _get_entry(sh):
    url = '%s/ledger/%s?receiver_id=%d' % (FIELD_SYSTEM_URL, sh.delivery_no, sh.receiver_id)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='GET'), timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def _confirm(db, sh, token, actor, **values):
    if _settle(db, sh.id, token, **values):
        record(db, actor, 'shipment.' + values['status'],
               {'id': sh.id, 'delivery_no': sh.delivery_no, 'seq': sh.seq})
        db.commit()

def attempt(db, shipment_id, mode='auto', actor='worker'):
    """推进一场：mode=auto 对账后未查到则原号重发；check 只对账；send 直接原号重发。"""
    sh = db.get(Shipment, shipment_id)
    if not sh:
        raise HTTPException(404, '外送场次不存在')
    if sh.status in TERMINAL:
        raise HTTPException(409, '本场已终结（%s），无需操作' % sh.status)
    if sh.status == 'sending':
        raise HTTPException(409, '本场发送中，请稍后')
    head = head_unresolved(db, sh.receiver_id)
    if not head or head.id != sh.id:
        raise HTTPException(409, '同一接收方前场未决，本场按顺序等待')
    prev_status = sh.status
    token = uuid.uuid4().hex
    if not _claim(db, sh.id, prev_status, token):
        return _reload(db, sh.id)  # 已被其他进程接管
    try:
        if prev_status == 'reconciling' and mode in ('auto', 'check'):
            try:
                entry = _get_entry(sh)
            except Exception as e:
                _settle(db, sh.id, token, status='reconciling',
                        last_error='对账请求失败：' + _brief(e),
                        next_attempt_at=time.time() + OUTBOUND_RETRY_SECONDS)
                return _reload(db, sh.id)
            if entry:
                if entry.get('fingerprint') == sh.fingerprint:
                    _confirm(db, sh, token, actor, status='success', resolved_at=time.time(), last_error='')
                else:
                    _confirm(db, sh, token, actor, status='conflict', resolved_at=time.time(),
                             last_error='对方入账内容与本场冻结内容不符，已隔离')
                return _reload(db, sh.id)
            if mode == 'check':
                _settle(db, sh.id, token, status='reconciling',
                        last_error='对方未查到该送达编号，可原号重试',
                        next_attempt_at=time.time() + OUTBOUND_RETRY_SECONDS)
                return _reload(db, sh.id)
            # auto：未查到则按原送达编号重发，对方幂等入账不重复
        try:
            receipt = _post_receive(sh)
        except Exception as e:
            _settle(db, sh.id, token, status='reconciling',
                    last_error='回执丢失或对方不可用：' + _brief(e),
                    next_attempt_at=time.time() + OUTBOUND_RETRY_SECONDS)
            return _reload(db, sh.id)
        if receipt.get('delivery_no') == sh.delivery_no and receipt.get('fingerprint') == sh.fingerprint:
            _confirm(db, sh, token, actor, status='success', resolved_at=time.time(), last_error='')
        else:
            _settle(db, sh.id, token, status='reconciling',
                    last_error='回执内容与本场冻结内容不符，转待对账',
                    next_attempt_at=time.time() + OUTBOUND_RETRY_SECONDS)
        return _reload(db, sh.id)
    except HTTPException:
        raise
    except Exception:
        logging.exception('Outbound attempt failed')
        _settle(db, sh.id, token, status='reconciling', last_error='发送执行异常，待对账',
                next_attempt_at=time.time() + OUTBOUND_RETRY_SECONDS)
        return _reload(db, sh.id)

def tick():
    """worker 周期：触发到期计划 → 恢复中断场次 → 各接收方仅推进最前未决场。"""
    with Session() as db:
        fire_due(db)
        sweep_stale(db)
        now = time.time()
        heads, seen = [], set()
        for sh in db.scalars(select(Shipment).where(Shipment.status.in_(UNRESOLVED))
                             .order_by(Shipment.receiver_id, Shipment.seq)):
            if sh.receiver_id not in seen:
                seen.add(sh.receiver_id)
                if sh.status in ('pending', 'reconciling') and sh.next_attempt_at <= now:
                    heads.append(sh.id)
    for shipment_id in heads:
        with Session() as db:
            try:
                attempt(db, shipment_id, mode='auto')
            except HTTPException:
                pass  # 并发接管或状态已变化，下一轮再处理
            except Exception:
                logging.exception('Outbound tick failed for shipment %s', shipment_id)
