import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def receiver_dict(r):
    return {k:getattr(r,k) for k in ['id','name','fault','created_at']}
def outbound_plan_dict(p):
    return {k:getattr(p,k) for k in ['id','name','job_id','receiver_id','interval_seconds','next_run','enabled','created_at']}
def shipment_dict(s):
    return {k:getattr(s,k) for k in ['id','plan_id','receiver_id','seq','delivery_no','fingerprint','status','attempts','next_attempt_at','last_error','created_at','updated_at','resolved_at']}
def field_entry_dict(e):
    return {k:getattr(e,k) for k in ['id','receiver_id','delivery_no','fingerprint','times','recorded_at','last_receive_at']}
