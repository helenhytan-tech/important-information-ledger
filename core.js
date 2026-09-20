(function(root){
const fields=['分类','名称','登录方式/名称','登录/绑定邮箱','登录/绑定电话','密码提示','昵称','备注','其他'];
function parsePaste(text,headers=fields){
 const rows=[];let row=[],cell='',quoted=false;
 for(let i=0;i<text.length;i++){
  const c=text[i];
  if(c==='"' && (quoted || cell==='')){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
  else if(!quoted&&(c==='\t'||c==='\n'||c==='\r')){row.push(cell);cell='';if(c!=='\t'){rows.push(row);row=[];if(c==='\r'&&text[i+1]==='\n')i++;}}
  else cell+=c;
 }
 row.push(cell);rows.push(row);
 while(rows.length&&rows.at(-1).every(v=>v===''))rows.pop();
 if(rows.length&&headers.every((v,i)=>rows[0][i]===v))rows.shift();
 return rows;
}
function rowToTSV(row){return row.map(value=>/["\t\r\n]/.test(value)?'"'+value.replace(/"/g,'""')+'"':value).join('\t');}
function matches(row,query,filters){return (!query||row.some(v=>v.toLocaleLowerCase().includes(query.toLocaleLowerCase())))&&filters.every((f,i)=>!f.value||(f.exact?row[i]===f.value:row[i].toLocaleLowerCase().includes(f.value.toLocaleLowerCase())));}
const api={fields,parsePaste,matches,rowToTSV};if(typeof module!=='undefined')module.exports=api;else root.Ledger=api;
})(globalThis);
