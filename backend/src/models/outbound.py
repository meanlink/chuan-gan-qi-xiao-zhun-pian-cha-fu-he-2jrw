from sqlalchemy import String, Double, ForeignKey, Boolean, JSON, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Receiver(Base):
    """现场系统接收端。fault 仅用于本地模拟对端故障。"""
    __tablename__ = 'receivers'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    fault: Mapped[str] = mapped_column(String(20), default='none')
    created_at: Mapped[float] = mapped_column(Double)
class OutboundPlan(Base):
    """外送计划：把批准后的结果按周期送入现场系统。"""
    __tablename__ = 'outbound_plans'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    receiver_id: Mapped[int] = mapped_column(ForeignKey('receivers.id'))
    interval_seconds: Mapped[int]
    next_run: Mapped[float] = mapped_column(Double)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(Double)
class Shipment(Base):
    """外送场次：每场冻结批准结果快照与送达编号，编号在重试间保持不变。"""
    __tablename__ = 'shipments'
    __table_args__ = (UniqueConstraint('receiver_id', 'delivery_no'), UniqueConstraint('receiver_id', 'seq'))
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('outbound_plans.id'))
    receiver_id: Mapped[int] = mapped_column(ForeignKey('receivers.id'))
    seq: Mapped[int] = mapped_column(Integer)
    delivery_no: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    attempt_token: Mapped[str] = mapped_column(String(64), default='')
    claimed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    next_attempt_at: Mapped[float] = mapped_column(Double, default=0)
    last_error: Mapped[str] = mapped_column(String(300), default='')
    created_at: Mapped[float] = mapped_column(Double)
    updated_at: Mapped[float] = mapped_column(Double)
    resolved_at: Mapped[float | None] = mapped_column(Double, nullable=True)
class FieldEntry(Base):
    """现场系统（本地模拟端）的入账台账，发送方不直接读写。"""
    __tablename__ = 'field_ledger'
    __table_args__ = (UniqueConstraint('receiver_id', 'delivery_no'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey('receivers.id'))
    delivery_no: Mapped[str] = mapped_column(String(40))
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    times: Mapped[int] = mapped_column(Integer, default=1)
    recorded_at: Mapped[float] = mapped_column(Double)
    last_receive_at: Mapped[float] = mapped_column(Double)
