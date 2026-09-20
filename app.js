const {parsePaste,matches,rowToTSV}=Ledger;
let fields=Ledger.fields;
const $=id=>document.getElementById(id);
let rows=[],revision=0,loaded=false,selection=null,history=[],timer,dirty=false,saving=false,conflict=false,version=0;
let filters=fields.map(()=>({value:'',exact:false}));
const tables={general:'信息记录',work:'工作',important:'重要',personal:'个人',other:'其他',computer:'电脑操作'};
let currentTable='general',switching=false;
// Cloudflare/GitHub Pages run this file without the local Python API. In that
// mode every table is kept in this browser's localStorage and moves between
// computers only through the JSON import/export controls.
const STATIC_MODE=location.protocol==='file:'||location.pathname.startsWith('/dist/')||!(location.hostname==='localhost'||location.hostname==='127.0.0.1'||location.hostname==='::1')||location.port!=='8766';
const localKey=key=>`information-ledger:${key}`;
const localBackupKey=key=>`information-ledger-backups:${key}`;
function tableFields(key){return key==='computer'?['产品','名称','操作方式','快捷键','备注','其他']:Ledger.fields;}
function validRows(value,key=currentTable){const expected=tableFields(key).length;return Array.isArray(value)&&value.length<=20000&&value.every(row=>Array.isArray(row)&&row.length===expected&&row.every(v=>typeof v==='string'&&v.length<=32767));}
function readLocalRows(key=currentTable){try{const parsed=JSON.parse(localStorage.getItem(localKey(key))||'null');return validRows(parsed,key)?parsed:null;}catch{return null;}}
function readLocalBackups(key=currentTable){try{const parsed=JSON.parse(localStorage.getItem(localBackupKey(key))||'[]');return Array.isArray(parsed)?parsed.filter(item=>validRows(item.rows,key)):[];}catch{return [];}}
function writeLocalBackup(data=rows){const list=readLocalBackups();list.unshift({id:crypto.randomUUID?.()||String(Date.now()),time:new Date().toISOString(),rows:JSON.parse(JSON.stringify(data)),fields:[...fields]});localStorage.setItem(localBackupKey(currentTable),JSON.stringify(list.slice(0,30)));}
function writeLocalRows(data=rows){localStorage.setItem(localKey(currentTable),JSON.stringify(data));localStorage.setItem(`${localKey(currentTable)}:revision`,String(revision));}
function api(url,options={}){return fetch(url,{...options,headers:{...options.headers,'X-Ledger-Table':currentTable}});}
const blank=()=>Array(fields.length).fill('');
const newRow=blank;
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('show'),3500);}
function showError(message){$('error').hidden=false;$('error').textContent=message;}
function remember(){history.push(JSON.stringify(rows));if(history.length>30)history.shift();$('undo').disabled=false;}
function changed(){dirty=true;version++;$('saveState').textContent='待保存…';clearTimeout(timer);timer=setTimeout(save,400);updateCounts();}
async function save(){
 if(!loaded||!dirty||saving||conflict||restoring)return;
 saving=true;const v=version;$('saveState').textContent='正在保存…';
 try{if(STATIC_MODE){writeLocalBackup(rows);revision++;writeLocalRows(rows);dirty=version!==v;$('error').hidden=true;$('saveState').textContent=dirty?'待保存…':'已保存到本机';return;}
 const res=await api('/api/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,rows})});const data=await res.json();if(!res.ok){if(res.status===409)conflict=true;throw Error(data.error);}
 revision=data.revision;dirty=version!==v;$('error').hidden=true;$('saveState').textContent=dirty?'待保存…':'已保存到本机';
 }catch(e){$('saveState').textContent='未保存';showError(e.message+' 可点击此处重试保存。');}
 finally{saving=false;if(dirty&&version!==v&&!conflict)await save();}
}
$('error').onclick=()=>save();
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
function visible(){return rows.map((row,i)=>({row,i})).filter(({row})=>matches(row,$('query').value.trim(),filters));}
function active(){return Boolean($('query').value.trim()||filters.some(f=>f.value));}
function updateCounts(){const count=rows.filter(r=>r.some(Boolean)).length;$('total').textContent=count;$('totalBadge').textContent=count;$('shown').textContent=visible().filter(({row})=>row.some(Boolean)).length;$('filterCount').textContent=filters.filter(f=>f.value).length;}
function expandCell(input){
 const wrap=input.closest('.table-wrap');
 const scrollTop=wrap?.scrollTop;
 input.style.height='65px';
 input.style.height=Math.max(65,input.scrollHeight+2)+'px';
 if(wrap)wrap.scrollTop=scrollTop;
}
window.addEventListener('resize',()=>{const input=document.activeElement;if(input?.matches('#sheet textarea'))expandCell(input);});
function render(){
 const table=$('sheet');table.replaceChildren();const head=table.createTHead().insertRow();['#',...fields].forEach(v=>{const th=document.createElement('th');th.scope='col';th.textContent=v;head.append(th);});
 const body=table.createTBody(),items=visible();
 for(const {row,i} of items){const tr=body.insertRow();if(selection?.row===i)tr.className='selected';const num=tr.insertCell();num.className='row-number';const rowButton=document.createElement('button');rowButton.className='row-select';rowButton.textContent=i+1;rowButton.setAttribute('aria-label',`选中第 ${i+1} 行`);rowButton.setAttribute('aria-pressed',String(selection?.row===i&&Boolean(selection?.whole)));num.append(rowButton);
 rowButton.onclick=()=>{selection={row:i,col:0,whole:true};render();document.querySelectorAll('.row-select')[visible().findIndex(item=>item.i===i)]?.focus();};
 if(selection?.row===i&&selection.whole)tr.classList.add('whole-row');
 row.forEach((value,c)=>{const td=tr.insertCell(),input=document.createElement('textarea');input.value=value;input.maxLength=32767;input.setAttribute('aria-label',`第 ${i+1} 行 ${fields[c]}`);input.dataset.row=i;input.dataset.col=c;input.spellcheck=false;
 input.addEventListener('focus',()=>{selection={row:i,col:c};document.querySelectorAll('tr.selected').forEach(el=>el.classList.remove('selected','whole-row'));document.querySelectorAll('.row-select').forEach(el=>el.setAttribute('aria-pressed','false'));$('copyRow').disabled=false;tr.classList.add('selected');$('selection').textContent=`第 ${i+1} 行 · ${fields[c]}`;$('delete').disabled=false;input.dataset.before=JSON.stringify(rows);expandCell(input);});
 input.addEventListener('blur',()=>{input.style.height='';});
 input.addEventListener('input',()=>{if(input.dataset.before){history.push(input.dataset.before);if(history.length>30)history.shift();delete input.dataset.before;$('undo').disabled=false;}rows[i][c]=input.value;expandCell(input);changed();});
 input.addEventListener('paste',e=>{const text=e.clipboardData.getData('text/plain');if(text.includes('\t')||text.includes('\n')||text.includes('\r')){e.preventDefault();if(applyPaste(text))focusCell(i,c);}});
 input.addEventListener('keydown',e=>{if(e.key==='Tab'&&!e.shiftKey&&c===fields.length-1&&i===rows.length-1&&!active()){e.preventDefault();remember();rows.push(newRow());changed();render();focusCell(rows.length-1,0);}});
 td.append(input);});}
 $('empty').hidden=items.length>0;updateCounts();$('undo').disabled=!history.length;$('delete').disabled=!selection;$('copyRow').disabled=!selection;if(selection?.whole)$('selection').textContent=`已选中第 ${selection.row+1} 行 · ⌘C / Ctrl+C 复制整行`;else if(!selection)$('selection').textContent='点击行号选择整行，点击单元格编辑';
}
function focusCell(r,c){const target=document.querySelector(`textarea[data-row="${r}"][data-col="${c}"]`);target?.focus();}
function reset(){filters.forEach((f,i)=>{f.value='';f.exact=false;$('filter-'+i).value='';});$('query').value='';selection=null;$('selection').textContent='点击单元格即可编辑';closeOptions();render();}
function applyPaste(text){
 if(!loaded)return;
 const matrix=parsePaste(text,fields);if(!matrix.length){toast('没有可填入的内容');return false;}
 const start=selection?.row??rows.length,col=selection?.col??0;
 if(matrix.some(r=>r.length+col>fields.length)){toast(`粘贴内容超出 ${fields.length} 列，请选择更靠左的单元格或减少列数。`);return false;}
 if(matrix.some(r=>r.some(v=>v.length>32767))||Math.max(rows.length,start+matrix.length)>20000){toast('内容超出容量，请减少行数或单元格长度。');return false;}
 const targets=selection?visible().map(v=>v.i).filter(i=>i>=start):[];
 if(active()&&selection&&matrix.length>targets.length){toast('筛选状态下粘贴行数超过可见行，请先重置筛选。');return false;}
 remember();
 matrix.forEach((row,k)=>{let target=active()&&selection?targets[k]:start+k;while(rows.length<=target)rows.push(newRow());row.forEach((v,c)=>rows[target][col+c]=v);});
 changed();render();toast(`已填入 ${matrix.length} 行`);return true;
}
function closeOptions(){document.querySelectorAll('.options').forEach(el=>el.hidden=true);}
function buildFilters(){
 $('filters').replaceChildren();filters=fields.map(()=>({value:'',exact:false}));
 fields.forEach((field,i)=>{
 const wrap=document.createElement('div');wrap.className='filter';const label=document.createElement('label');label.htmlFor='filter-'+i;label.textContent=field;
 const group=document.createElement('div');group.className='filter-input';const input=document.createElement('input');input.id='filter-'+i;input.type='search';input.placeholder='搜索或点选';input.autocomplete='off';input.setAttribute('aria-label',`筛选${field}`);
 const arrow=document.createElement('button');arrow.textContent='⌄';arrow.className='arrow';arrow.setAttribute('aria-label',`展开${field}选项`);
 const options=document.createElement('div');options.className='options';options.hidden=true;
 function populate(){closeOptions();options.replaceChildren();options.hidden=false;
 const values=[...new Set(rows.map(r=>r[i]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN')).filter(v=>v.toLowerCase().includes(input.value.toLowerCase()));
 const clear=document.createElement('button');clear.textContent='全部（清除此条件）';clear.onclick=()=>{input.value='';filters[i]={value:'',exact:false};options.hidden=true;selection=null;render();};options.append(clear);
 for(const value of values){const b=document.createElement('button');b.textContent=value;b.onclick=()=>{input.value=value;filters[i]={value,exact:true};options.hidden=true;selection=null;render();};options.append(b);}
 if(!values.length){const p=document.createElement('p');p.textContent='无匹配选项，按输入关键词搜索';options.append(p);}}
 input.oninput=()=>{filters[i]={value:input.value,exact:false};selection=null;populate();render();};input.onfocus=populate;arrow.onclick=()=>options.hidden?populate():closeOptions();input.onkeydown=e=>{if(e.key==='Escape')closeOptions();if(e.key==='ArrowDown'){e.preventDefault();if(options.hidden)populate();options.querySelector('button')?.focus();}};
 group.append(input,arrow);wrap.append(label,group,options);$('filters').append(wrap);
});
}
buildFilters();
document.addEventListener('click',e=>{if(!e.target.closest('.filter'))closeOptions();});
$('query').oninput=()=>{selection=null;render();};$('reset').onclick=reset;
$('toggleFilters').onclick=()=>{$('filterPanel').hidden=!$('filterPanel').hidden;};
async function navigate(){
 const key=location.hash.slice(1)||'all';
 const target=Object.hasOwn(tables,key)?key:(key==='filter'?currentTable:'general');
 const canonical=()=>currentTable==='general'?'all':currentTable;
 if(switching||restoring){window.history.replaceState(null,'','#'+canonical());return;}
 if(target!==currentTable&&saving){toast('正在保存，请稍后再切换表格');window.history.replaceState(null,'','#'+canonical());return;}
 switching=true;
 try{
  if(target!==currentTable&&dirty){await save();if(dirty){toast('当前表未保存，暂不能切换。请先下载备份或重试保存。');window.history.replaceState(null,'','#'+canonical());return;}}
  const mustLoad=target!==currentTable||!loaded;
  if(target!==currentTable){$('backupDialog').close();$('pasteDialog').close();}
  currentTable=target;
  fields=currentTable==='computer'?['产品','名称','操作方式','快捷键','备注','其他']:Ledger.fields;buildFilters();
  $('sheet').classList.toggle('computer-table',currentTable==='computer');
  document.querySelectorAll('[data-view]').forEach(b=>{const on=b.dataset.view===(key==='filter'?'filter':canonical());b.classList.toggle('active',on);if(on)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  $('viewTitle').textContent=tables[currentTable];$('filterPanel').hidden=key!=='filter';
  $('query').placeholder=currentTable==='computer'?'搜索产品、名称、操作方式、快捷键…':`搜索${tables[currentTable]}表中的名称、邮箱、电话…`;
  $('empty').textContent=`${tables[currentTable]}表暂无符合条件的记录。可新增记录或重置筛选。`;
  $('exportAll').textContent='导出当前表';$('backupTitle').textContent=tables[currentTable]+' · 备份与恢复';
  if(mustLoad){clearTimeout(timer);rows=[];loaded=false;dirty=false;conflict=false;history=[];selection=null;backupToken=null;restoreSource=null;$('add').disabled=true;$('paste').disabled=true;$('error').hidden=true;reset();await init();}else reset();
 }finally{switching=false;}
}
window.addEventListener('hashchange',navigate);
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(location.hash.slice(1)===b.dataset.view)navigate();else location.hash=b.dataset.view;});

$('add').onclick=()=>{if(!loaded)return;reset();remember();rows.push(newRow());changed();render();focusCell(rows.length-1,0);};
$('undo').onclick=()=>{if(!history.length)return;rows=JSON.parse(history.pop());selection=null;changed();render();toast('已撤销上一步');};
$('copyRow').onclick=async()=>{
 if(!selection||!rows[selection.row])return;
 const text=rowToTSV(rows[selection.row]);
 try{await navigator.clipboard.writeText(text);toast('已复制整行，可粘贴到 Excel 或其他表格');}
 catch(e){$('copyText').value=text;$('copyDialog').showModal();$('copyText').focus();$('copyText').select();}
};
document.addEventListener('copy',e=>{
 if(!selection?.whole||!rows[selection.row]||document.querySelector('dialog[open]'))return;
 const target=document.activeElement;if(target?.matches('input,textarea,[contenteditable="true"]'))return;
 if(!e.clipboardData)return;
 e.preventDefault();e.clipboardData.setData('text/plain',rowToTSV(rows[selection.row]));toast('已复制整行');
});
$('delete').onclick=()=>{if(!selection)return;remember();rows.splice(selection.row,1);selection=null;changed();render();toast('已删除，可点击“撤销上一步”恢复');};
$('paste').onclick=()=>{$('pasteText').value='';$('pasteDialog').showModal();$('pasteText').focus();};
$('applyPaste').onclick=()=>{if(applyPaste($('pasteText').value))$('pasteDialog').close();};
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function htmlSection(title,columns,data){return `<section class="export-section"><h1>${esc(title)}</h1><table><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${data.map(row=>`<tr>${row.map(v=>`<td>${esc(v).replace(/\n/g,'<br>')}</td>`).join('')}</tr>`).join('')}</tbody></table></section>`;}
function exportDocument(title,sections,format){
 const body=sections.map(s=>htmlSection(s.title,s.fields,s.rows)).join('');
 const html=`<!doctype html><meta charset="utf-8"><title>${esc(title)}</title><style>body{font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#18212f;padding:24px}.export-section{margin-bottom:36px;page-break-after:always}.export-section:last-child{page-break-after:auto}h1{font-size:22px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:7px;vertical-align:top;text-align:left;white-space:pre-wrap}th{background:#e8eef7}@media print{body{padding:0}.export-section{page-break-after:always}}</style>${body}`;
 const stamp=new Date().toISOString().slice(0,10);
 if(format==='html'){downloadBlob(new Blob([html],{type:'text/html;charset=utf-8'}),`${title}-${stamp}.html`);return 'html';}
 if(format==='xlsx'){downloadBlob(new Blob([html],{type:'application/vnd.ms-excel'}),`${title}-${stamp}.xls`);return 'xls';}
 if(format==='pdf'){const win=window.open('','_blank');if(!win)throw Error('浏览器阻止了新窗口，请允许弹出窗口后重试');win.document.write(html);win.document.close();win.focus();setTimeout(()=>win.print(),250);return 'pdf';}
 if(format==='png'){
  const width=1800,rowHeight=34,rowsForImage=sections.flatMap(s=>[[s.title],s.fields,...s.rows]);const canvas=document.createElement('canvas');canvas.width=width;canvas.height=Math.max(220,Math.min(12000,80+rowsForImage.length*rowHeight));const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,width,canvas.height);ctx.font='16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';let y=34;
  for(const section of sections){ctx.font='bold 22px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';ctx.fillStyle='#18212f';ctx.fillText(section.title,24,y);y+=rowHeight;ctx.font='bold 14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';ctx.fillStyle='#e8eef7';ctx.fillRect(20,y-25,width-40,rowHeight);ctx.fillStyle='#18212f';section.fields.forEach((v,i)=>ctx.fillText(String(v),28+i*(width-40)/section.fields.length,y));y+=rowHeight;ctx.font='14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';for(const row of section.rows){ctx.fillStyle='#18212f';row.forEach((v,i)=>ctx.fillText(String(v).slice(0,80),28+i*(width-40)/section.fields.length,y));y+=rowHeight;}y+=12;}
  canvas.toBlob(blob=>{if(blob)downloadBlob(blob,`${title}-${stamp}.png`);},'image/png');return 'png';
 }
 throw Error('不支持的导出格式');
}
function staticSections(filtered=false){const selected=(filtered?visible().map(v=>v.row):rows).filter(r=>r.some(Boolean));return [{title:tables[currentTable],fields:[...fields],rows:selected}];}
async function exportRows(filtered){
 const format=$('exportFormat').value,exportLabel=tables[currentTable];
 $('exportAll').disabled=true;$('exportFiltered').disabled=true;toast('正在生成导出文件…');
 if(!loaded){toast('记录尚未读取完成');$('exportAll').disabled=false;$('exportFiltered').disabled=false;return;}
 const selected=(filtered?visible().map(v=>v.row):rows).filter(r=>r.some(Boolean));
 try{if(STATIC_MODE){const extension=exportDocument(`${tables[currentTable]}-${filtered?'筛选结果':'全部记录'}`,staticSections(filtered),format);toast(format==='pdf'?'已打开打印窗口，请选择“存储为 PDF”':`已导出 ${selected.length} 条记录（${extension.toUpperCase()}）`);return;}
 const res=await api('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows:selected,format})});if(!res.ok){const data=await res.json();throw Error(data.error);}
 const blob=await res.blob();const extension=blob.type.includes('zip')?'zip':format;const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`${exportLabel}-${filtered?'筛选结果':'全部记录'}-${new Date().toLocaleDateString('sv-SE')}.${extension}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);toast(`已导出 ${selected.length} 条记录${extension==='zip'?'，多页 PNG 已打包为 ZIP':''}`);
 }catch(e){showError('导出失败：'+e.message);}finally{$('exportAll').disabled=false;$('exportFiltered').disabled=false;}}
$('exportAll').onclick=()=>exportRows(false);$('exportFiltered').onclick=()=>exportRows(true);
async function exportAllTables(){
 const format=$('exportFormat').value;
 $('exportAllTables').disabled=true;toast('正在生成全部表格…');
 try{if(STATIC_MODE){const sections=Object.entries(tables).map(([key,title])=>({title,fields:tableFields(key),rows:(key===currentTable?rows:readLocalRows(key)||[]).filter(r=>r.some(Boolean))}));const extension=exportDocument('重要信息-全部表格',sections,format);toast(format==='pdf'?'已打开打印窗口，请选择“存储为 PDF”':`已导出全部表格（${extension.toUpperCase()}）`);return;}
  const res=await api('/api/export-all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format})});
  if(!res.ok){const data=await res.json();throw Error(data.error);}
  const blob=await res.blob(),extension=blob.type.includes('zip')?'zip':format;
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`重要信息-全部表格-${new Date().toLocaleDateString('sv-SE')}.${extension}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
  toast(`已导出全部表格${extension==='zip'?'，PNG 页面已打包为 ZIP':''}`);
 }catch(e){showError('导出全部表格失败：'+e.message);}finally{$('exportAllTables').disabled=false;}
}
$('exportAllTables').onclick=exportAllTables;
async function init(){try{if(STATIC_MODE){rows=readLocalRows()||[];revision=Number(localStorage.getItem(`${localKey(currentTable)}:revision`)||0);loaded=true;if(!rows.length)rows=[blank(),blank(),blank(),blank(),blank()];$('saveState').textContent='已读取本机记录';$('add').disabled=false;$('paste').disabled=false;render();return;}
 const res=await api('/api/records');const data=await res.json();if(!res.ok)throw Error(data.error);rows=data.rows;revision=data.revision;loaded=true;if(!rows.length)rows=[blank(),blank(),blank(),blank(),blank()];$('saveState').textContent='已读取本机记录';$('add').disabled=false;$('paste').disabled=false;render();}catch(e){showError('读取失败：'+e.message+' 请重新打开页面。');$('saveState').textContent='读取失败';}}


// Recoverable disk snapshots and portable backups.
let restoring=false,backupToken=null,restoreSource=null;
function portableBackup(data){return {format:'information-ledger-v1',table:currentTable,fields,createdAt:new Date().toISOString(),rows:data};}
function downloadBackup(){
 if(!loaded){toast('当前记录未能读取，请先预览历史备份');return;}
 const blob=new Blob([JSON.stringify(portableBackup(rows),null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=tables[currentTable]+'表备份-'+new Date().toISOString().replace(/[:.]/g,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 toast('已下载当前内容，包括尚未保存的修改');
}
function previewBackup(data,source,title){
 if(!data||!Array.isArray(data.rows)||data.rows.length>20000||data.rows.some(r=>!Array.isArray(r)||r.length!==fields.length||r.some(v=>typeof v!=='string'||v.length>32767)))throw Error('备份内容格式不正确');
 restoreSource=source;$('backupPreview').hidden=false;$('previewTitle').textContent=title;
 $('previewCount').textContent=`共 ${data.rows.filter(r=>r.some(Boolean)).length} 条记录，下面预览前 20 行。`;
 const table=$('previewTable');table.replaceChildren();const head=table.createTHead().insertRow();fields.forEach(f=>{const th=document.createElement('th');th.textContent=f;head.append(th);});
 const body=table.createTBody();data.rows.slice(0,20).forEach(row=>{const tr=body.insertRow();row.forEach(v=>{const td=tr.insertCell();td.textContent=v;});});
 $('restoreBackup').disabled=!backupToken;
}
async function loadBackups(){
 backupToken=null;restoreSource=null;$('backupPreview').hidden=true;$('backupList').replaceChildren();$('backupStatus').textContent='正在读取历史备份…';
 try{if(STATIC_MODE){const data=readLocalBackups();backupToken='local';$('backupStatus').textContent=data.length?'选择一个版本，先预览再恢复。':'暂无历史备份，首次保存后会自动生成。';data.forEach(item=>{const row=document.createElement('div');row.className='backup-row';const text=document.createElement('span');text.textContent=`${new Date(item.time).toLocaleString()} · ${item.rows.filter(r=>r.some(Boolean)).length} 条记录`;const button=document.createElement('button');button.textContent='预览';button.onclick=()=>previewBackup({format:'information-ledger-v1',table:currentTable,fields:[...fields],rows:item.rows},{backupId:item.id},new Date(item.time).toLocaleString()+' 的备份');row.append(text,button);$('backupList').append(row);});return;}
 const res=await api('/api/backups');const data=await res.json();if(!res.ok)throw Error(data.error);backupToken=data.token;
 $('backupStatus').textContent=data.backups.length?'选择一个版本，先预览再恢复。':'暂无历史备份，首次保存后会自动生成。';
 data.backups.forEach(item=>{const row=document.createElement('div');row.className='backup-row';const text=document.createElement('span');text.textContent=item.valid?`${new Date(item.time).toLocaleString()} · ${item.count} 条记录`:'备份文件损坏，无法恢复';const button=document.createElement('button');button.textContent='预览';button.disabled=!item.valid;
 button.onclick=async()=>{button.disabled=true;try{const res=await api('/api/backup?id='+encodeURIComponent(item.id));const data=await res.json();if(!res.ok)throw Error(data.error);previewBackup(data,{backupId:item.id},new Date(item.time).toLocaleString()+' 的备份');}catch(e){$('backupStatus').textContent=e.message;}finally{button.disabled=false;}};
 row.append(text,button);$('backupList').append(row);});
 }catch(e){$('backupStatus').textContent='备份列表读取失败：'+e.message;}
}
$('backupsButton').onclick=async()=>{$('backupDialog').showModal();await loadBackups();};
$('closeBackups').onclick=()=>{if(!restoring)$('backupDialog').close();};
$('downloadBackup').onclick=downloadBackup;
function chooseJson(){$('backupFile').value='';$('backupFile').click();}
$('importBackup').onclick=chooseJson;
$('importJsonButton').onclick=chooseJson;
$('backupFile').onchange=async()=>{
 const file=$('backupFile').files[0];if(!file)return;
 const tableAtStart=currentTable;
 if(!$('backupDialog').open)$('backupDialog').showModal();
 await loadBackups();
 try{
  if(file.size>20000000)throw Error('JSON 文件过大');
  let data=JSON.parse((await file.text()).replace(/^\uFEFF/,''));
  if(currentTable!==tableAtStart)return;
  if(Array.isArray(data))data={rows:data};
  if(!data||typeof data!=='object')throw Error('请选择包含 rows 数组的记录文件或二维数组');
  if(data.table&&data.table!==currentTable)throw Error('文件属于'+(tables[data.table]||'另一张表')+'，请切换到该表导入');
  if(data.format&&data.format!=='information-ledger-v1')throw Error('不支持此 JSON 文件格式');
  if(data.fields&&JSON.stringify(data.fields)!==JSON.stringify(fields))throw Error('文件列名与当前表不一致，请切换到对应表');
  const source={format:'information-ledger-v1',table:currentTable,fields,rows:data.rows};
  previewBackup(source,source,'JSON 导入预览：'+file.name);
  $('backupStatus').textContent='请核对列顺序和内容。确认恢复将替换当前表，并自动备份原内容。';
 }catch(e){restoreSource=null;$('backupPreview').hidden=true;$('backupStatus').textContent=e.message;}
};
$('restoreBackup').onclick=async()=>{
 if(!restoreSource||!backupToken||restoring)return;
 if(saving){$('backupStatus').textContent='正在保存，请保存完成后重新打开此窗口再恢复。';return;}
 if(dirty){$('backupStatus').textContent='当前有未保存的修改。请先下载当前内容备份，并完成保存后再恢复。';return;}
 restoring=true;clearTimeout(timer);$('restoreBackup').disabled=true;$('closeBackups').disabled=true;
 try{if(STATIC_MODE){writeLocalBackup(rows);rows=JSON.parse(JSON.stringify(restoreSource.rows));revision++;writeLocalRows(rows);loaded=true;dirty=false;conflict=false;history=[];selection=null;version++;$('error').hidden=true;$('saveState').textContent='已恢复并保存到本机';$('add').disabled=false;$('paste').disabled=false;reset();$('backupDialog').close();toast('已恢复，恢复前的记录也已备份');return;}
 const res=await api('/api/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...restoreSource,token:backupToken})});const data=await res.json();if(!res.ok)throw Error(data.error);
 rows=data.rows;revision=data.revision;loaded=true;dirty=false;conflict=false;history=[];selection=null;version++;$('error').hidden=true;$('saveState').textContent='已恢复并保存到本机';$('add').disabled=false;$('paste').disabled=false;reset();$('backupDialog').close();toast('已恢复，恢复前的记录也已备份');
 }catch(e){$('backupStatus').textContent='恢复未确认成功：'+e.message+' 请重新打开备份与恢复核对。';backupToken=null;}
 finally{restoring=false;$('restoreBackup').disabled=!backupToken;$('closeBackups').disabled=false;}
};
$('backupDialog').addEventListener('cancel',e=>{if(restoring)e.preventDefault();});
navigate();
