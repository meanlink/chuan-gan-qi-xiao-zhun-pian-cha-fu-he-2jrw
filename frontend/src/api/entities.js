import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const outbound={
 receivers:()=>api('/receivers'),
 createReceiver:data=>api('/receivers',{method:'POST',body:JSON.stringify(data)}),
 setFault:(id,fault)=>api('/receivers/'+id+'/fault',{method:'POST',body:JSON.stringify({fault})}),
 plans:()=>api('/outbound-plans'),
 createPlan:data=>api('/outbound-plans',{method:'POST',body:JSON.stringify(data)}),
 togglePlan:id=>api('/outbound-plans/'+id+'/toggle',{method:'POST'}),
 fire:id=>api('/outbound-plans/'+id+'/fire',{method:'POST'}),
 shipments:()=>api('/shipments'),
 reconcile:id=>api('/shipments/'+id+'/reconcile',{method:'POST'}),
 retry:id=>api('/shipments/'+id+'/retry',{method:'POST'}),
 ledger:()=>api('/field-ledger'),
};
