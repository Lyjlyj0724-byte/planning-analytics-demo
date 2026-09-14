const $=s=>document.querySelector(s),node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
let csrf='',state={},batch=null,history=false,filters={},loading=false;
const names={collecting:'生成合成数据',validating:'数据校验',ingesting:'模拟入库',succeeded:'刷新成功',failed:'刷新失败',interrupted:'结果未确认'};
async function api(path,body){const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d}
function table(target,labels,rows){const head=node('thead'),tr=node('tr'),body=node('tbody');labels.forEach(x=>tr.append(node('th',x)));head.append(tr);rows.forEach(row=>{const r=node('tr');row.forEach(v=>r.append(node('td',v??'—')));body.append(r)});target.replaceChildren(head,body)}
function query(){return new URLSearchParams({batch,...filters}).toString()}
function renderStatus(){const r=state.latest;$('#status').replaceChildren(node('p',r?`${names[r.state]} · ${r.message} · 请求时间 ${r.requested_at}`:'还没有运行记录。请选择场景开始演示。'));$('#status').className=r?.state==='failed'?'failure':'';$('#history').hidden=!state.last_success;$('#events').replaceChildren(...state.events.map(e=>node('li',names[e.stage]||e.stage)));table($('#ledger'),['请求时间','场景','状态','返回条数','说明'],state.recent.map(r=>[r.requested_at,r.scenario,names[r.state],r.rows,r.message]))}
async function renderView(){
 const d=await api('/api/view?'+query());$('#analysisSection').hidden=false;
 $('#scope').textContent=`${history?'历史成功快照，不代表本次刷新成功':'本次成功批次'} · 仅合成数据 · ${d.batch_id} · 合成数据基准时间 ${d.source_at} · 当前 ${d.rows.length}/${d.original_records} 条 · 筛选 ${JSON.stringify(d.filters)}`;
 for(const key of ['region','department']){const select=$('#'+key);select.replaceChildren(new Option('全部',''),...d.options[key].map(x=>new Option(x,x)));select.value=filters[key]||''}
 $('#metrics').replaceChildren(...d.analysis.metrics.map(m=>{const card=node('article');card.className='metric';card.append(node('div',m.label),node('strong',m.value===null?'不计算':m.value+(m.unit==='%'?'%':'')),node('small',m.unit));return card}));
 const max=Math.max(1,...d.analysis.groups.map(g=>g.amount));$('#groups').replaceChildren(...d.analysis.groups.map(g=>{const bar=node('div');bar.className='bar';const fill=node('span');fill.style.width=(g.amount/max*100)+'%';bar.append(node('div',g.region),fill,node('b',g.amount));return bar}));
 $('#evidence').replaceChildren(node('p',d.analysis.approval),node('p','口径版本：'+d.analysis.version));
 if(!d.rows.length)$('#evidence').append(node('p','当前筛选没有记录，不生成完成情况结论；阶段合计为 0 不代表没有业务风险。'));
 for(const m of d.analysis.metrics){const detail=node('details');detail.append(node('summary','数据依据：'+m.label),node('p','公式：'+m.formula),node('p',`参与 ${d.rows.length} 条记录；${m.denominator!==undefined?`分子 ${m.numerator} / 分母 ${m.denominator}`:`合计 ${m.value}`}`));$('#evidence').append(detail)}
 $('#evidence').append(node('p','核查建议（非制度要求）：结合明细定位未完成环节，再由业务人员核对。暂无正式制度出处。'),...d.analysis.caveats.map(c=>node('p',c)));
 table($('#rows'),['合成记录','区域','部门','总个数','已完成','面料未完成','毛坯未完成','投染未完成'],d.rows.map(r=>[r.record_id,r.region,r.department,r.total,r.completed,r.material,r.blank,r.dye]));
}
async function guarded(fn){if(loading)return;loading=true;$('#error').textContent='';document.querySelectorAll('button,select').forEach(n=>n.disabled=true);try{await fn()}catch(e){$('#error').textContent=e.message;$('#analysisSection').hidden=true}finally{loading=false;document.querySelectorAll('button,select').forEach(n=>n.disabled=false)}}
$('#refresh').onclick=()=>guarded(async()=>{state=await api('/api/refresh',{scenario:$('#scenario').value});renderStatus();filters={};history=false;batch=state.latest?.state==='succeeded'?state.latest.batch_id:null;$('#analysisSection').hidden=true;if(batch)await renderView()});
$('#history').onclick=()=>guarded(async()=>{batch=state.last_success.batch_id;history=true;filters={};await renderView()});
for(const key of ['region','department'])$('#'+key).onchange=()=>guarded(async()=>{if($('#'+key).value)filters[key]=$('#'+key).value;else delete filters[key];await renderView()});
$('#export').onclick=()=>guarded(async()=>{const r=await fetch('/api/export?'+query());if(!r.ok)throw Error('导出失败');const url=URL.createObjectURL(await r.blob()),a=node('a');a.href=url;a.download='synthetic-planning.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
guarded(async()=>{state=await api('/api/status');csrf=state.csrf;renderStatus();if(state.latest?.state==='succeeded'){batch=state.latest.batch_id;await renderView()}});
