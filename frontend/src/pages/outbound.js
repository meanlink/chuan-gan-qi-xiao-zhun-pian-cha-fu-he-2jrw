import {jobs,outbound} from '../api/entities.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {ShipmentStatus,ReceiverFault} from '../constants/enums.js';
const fp=v=>'<code class="fp">'+esc(String(v||'').slice(0,16))+'…</code>';
const shipStatus=s=>'<span class="status ship-'+esc(s)+'">'+esc(ShipmentStatus[s]||s)+'</span>';
export async function outboundPage(){
 const [plans,receivers,shipments,ledger,allJobs]=await Promise.all([outbound.plans(),outbound.receivers(),outbound.shipments(),outbound.ledger(),jobs.list()]);
 const admin=session.user.role==='admin';
 const approved=allJobs.filter(j=>j.approved&&j.status==='completed');
 const rxName={};receivers.forEach(r=>rxName[r.id]=r.name);
 const planName={};plans.forEach(p=>planName[p.id]=p.name);
 const byNo={};ledger.forEach(e=>byNo[e.receiver_id+':'+e.delivery_no]=e);
 const faultButtons=r=>Object.keys(ReceiverFault).map(f=>'<button class="button small fault-btn'+(r.fault===f?' active':'')+'" data-receiver="'+r.id+'" data-fault="'+f+'" '+(admin?'':'disabled')+'>'+esc(ReceiverFault[f])+'</button>').join('');
 const checkCell=s=>{const e=byNo[s.receiver_id+':'+s.delivery_no];if(!e)return '<span class="check none">对方未入账</span>';return e.fingerprint===s.fingerprint?'<span class="check ok">双方一致</span>':'<span class="check bad">异内容</span>';};
 const actionCell=s=>{
  if(!admin)return '<span class="muted-cell">仅负责人操作</span>';
  if(s.status==='reconciling')return '<button class="text-button" data-reconcile="'+s.id+'">对账</button><button class="text-button" data-retry="'+s.id+'">原号重试</button>';
  if(s.status==='pending')return '<span class="muted-cell">等待调度</span>';
  if(s.status==='sending')return '<span class="muted-cell">发送中…</span>';
  if(s.status==='conflict')return '<span class="check bad">已隔离</span>';
  return '<span class="check ok">已确认</span>';};
 const shipRows=shipments.map(s=>{const e=byNo[s.receiver_id+':'+s.delivery_no];
  return '<tr><td>第 '+s.seq+' 场<br><small>'+esc(rxName[s.receiver_id]||'')+'</small></td><td><code class="fp">'+esc(s.delivery_no)+'</code><br><small>'+esc(planName[s.plan_id]||'')+'</small></td><td>'+fp(s.fingerprint)+'</td><td>'+(e?fp(e.fingerprint):'<span class="muted-cell">—</span>')+'</td><td>'+checkCell(s)+'</td><td>'+shipStatus(s.status)+(s.last_error?'<br><small class="err-note">'+esc(s.last_error)+'</small>':'')+'</td><td>'+s.attempts+'</td><td><small>'+date(s.updated_at)+'</small></td><td class="actions">'+actionCell(s)+'</td></tr>';}).join('');
 const ledgerRows=ledger.map(e=>'<tr><td><code class="fp">'+esc(e.delivery_no)+'</code></td><td>'+esc(rxName[e.receiver_id]||'')+'</td><td>'+fp(e.fingerprint)+'</td><td>'+date(e.recorded_at)+'</td><td>'+e.times+'</td></tr>').join('');
 return heading('06 / FIELD SYNC','外送与对账','简报按场次送入现场系统（本地模拟端）。每场冻结批准结果与送达编号；回执丢失转待对账，同编号同内容才确认成功，异内容隔离，未查到可原号重试。','<button class="button" id="refresh-outbound">刷新外送 ↻</button>')
 +'<div class="outbound-grid"><section class="panel"><div class="section-title"><h2>接收端 · 本地模拟现场系统</h2><span>'+receivers.length+' 个接收端</span></div>'
 +receivers.map(r=>'<article class="receiver"><div><strong>'+esc(r.name)+'</strong><p>当前故障模拟：'+esc(ReceiverFault[r.fault]||r.fault)+'</p></div><div class="fault-modes">'+faultButtons(r)+'</div></article>').join('')
 +'<p class="hint">丢失回执＝对方已入账但回执未返回；入账异内容＝对方台账内容与冻结内容不符；不可用＝对方不入账。同一接收方按场次顺序处理，前场未决时后场等待。</p></section>'
 +'<section class="panel"><div class="section-title"><h2>创建外送计划</h2></div><form id="outbound-form"><label>计划名称<input name="name" required minlength="2" value="现场复核简报外送"></label><label>已批准分析<select name="job_id" required>'+approved.map(j=>'<option value="'+j.id+'">'+esc(j.name)+'</option>').join('')+'</select></label><label>现场接收端<select name="receiver_id" required>'+receivers.map(r=>'<option value="'+r.id+'">'+esc(r.name)+'</option>').join('')+'</select></label><div class="parameter-grid"><label>外送周期<select name="interval_seconds"><option value="86400">每日</option><option value="604800">每周</option><option value="60">每分钟（验收）</option></select></label><label>首次执行<select name="delay_seconds"><option value="0">立即</option><option value="60">1 分钟后</option><option value="3600">1 小时后</option></select></label></div><button type="submit" class="primary" '+(admin&&approved.length&&receivers.length?'':'disabled')+'>保存外送计划</button></form>'
 +'<div class="section-title"><h2>运行中的外送计划</h2><span>'+plans.filter(p=>p.enabled).length+' 条已启用</span></div><div class="schedule-list">'+plans.map(p=>'<article><div><strong>'+esc(p.name)+'</strong><p>'+esc(rxName[p.receiver_id]||'')+'</p><small>下次 '+date(p.next_run)+' · 周期 '+p.interval_seconds+' 秒</small></div><div class="plan-actions"><button class="button small" data-fire="'+p.id+'" '+(admin?'':'disabled')+'>立即外送一场</button><button class="button small" data-toggle-plan="'+p.id+'" '+(admin?'':'disabled')+'>'+(p.enabled?'暂停':'启用')+'</button></div></article>').join('')+'</div></section></div>'
 +'<section class="panel"><div class="section-title"><h2>外送场次</h2><span>待发 / 待对账 / 冲突 / 成功 · 同一接收方按场次顺序</span></div>'
 +(shipments.length?'<div class="table-wrap"><table><thead><tr><th>场次</th><th>送达编号</th><th>本地指纹</th><th>对方指纹</th><th>核对</th><th>状态</th><th>尝试</th><th>更新</th><th>操作</th></tr></thead><tbody>'+shipRows+'</tbody></table></div>':'<p class="empty">尚无外送场次。创建计划并等待到期，或点击「立即外送一场」。</p>')+'</section>'
 +'<section class="panel"><div class="section-title"><h2>对方台账 · 现场系统入账记录</h2><span>'+ledger.length+' 条入账</span></div>'
 +(ledger.length?'<div class="table-wrap"><table><thead><tr><th>送达编号</th><th>接收端</th><th>入账指纹</th><th>入账时间</th><th>接收次数</th></tr></thead><tbody>'+ledgerRows+'</tbody></table></div>':'<p class="empty">现场系统尚未入账。接收次数大于 1 而台账仅一条，说明原号重试未重复入账。</p>')+'</section>';
}
export function bindOutbound(refresh){
 document.querySelector('#refresh-outbound').onclick=refresh;
 submit(document.querySelector('#outbound-form'),async f=>{await outbound.createPlan({name:f.get('name'),job_id:Number(f.get('job_id')),receiver_id:Number(f.get('receiver_id')),interval_seconds:Number(f.get('interval_seconds')),delay_seconds:Number(f.get('delay_seconds'))});notify('外送计划已保存，到期后自动产生场次');await refresh();});
 document.querySelectorAll('.fault-btn').forEach(b=>b.onclick=async()=>{try{await outbound.setFault(b.dataset.receiver,b.dataset.fault);notify('接收端故障模拟已切换为「'+ReceiverFault[b.dataset.fault]+'」');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-toggle-plan]').forEach(b=>b.onclick=async()=>{try{await outbound.togglePlan(b.dataset.togglePlan);await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-fire]').forEach(b=>b.onclick=async()=>{try{const sh=await outbound.fire(b.dataset.fire);notify('已产生第 '+sh.seq+' 场，送达编号 '+sh.delivery_no);await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-reconcile]').forEach(b=>b.onclick=async()=>{try{const sh=await outbound.reconcile(b.dataset.reconcile);notify('对账完成：'+ShipmentStatus[sh.status]+(sh.last_error?' · '+sh.last_error:''));await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{try{const sh=await outbound.retry(b.dataset.retry);notify('原号重试完成：'+ShipmentStatus[sh.status]+(sh.last_error?' · '+sh.last_error:''));await refresh();}catch(e){notify(e.message,true);}});
}
