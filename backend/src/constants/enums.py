from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class ShipmentStatus(str, Enum):
    pending = 'pending'          # 待发
    sending = 'sending'          # 发送中（执行占用，崩溃后恢复为待对账）
    reconciling = 'reconciling'  # 待对账
    conflict = 'conflict'        # 冲突 · 已隔离（终态）
    success = 'success'          # 成功（终态）
class ReceiverFault(str, Enum):
    none = 'none'                # 正常回执
    lose_receipt = 'lose_receipt'  # 入账但丢失回执
    tamper = 'tamper'            # 入账异内容
    unavailable = 'unavailable'  # 接收端不可用（不入账）
