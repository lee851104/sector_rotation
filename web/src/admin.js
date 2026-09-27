const status=document.getElementById('admin-status'),button=document.getElementById('refresh'),link=document.getElementById('run-link');
let busy=false,authorized=false,queueUntil=0;
const labels={running:'更新中',success:'行情更新成功',no_new_data:'目前沒有新行情',already_updated:'今日已更新',failed:'更新失敗，保留上次結果',quota_exhausted:'今日資料額度不足',queued:'等待執行'};
async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});if(!r.headers.get('content-type')?.includes('application/json'))throw new Error('請完成管理者登入，或確認 Cloudflare Access 與後端已設定。');const d=await r.json();if(!r.ok)throw new Error(d.error||'更新服務暫時無法使用');return d;}
async function poll(){if(document.hidden)return;try{const data=await api('/api/admin/status');authorized=true;const run=data.run;busy=run&&['queued','in_progress','waiting','pending','requested'].includes(run.status);button.disabled=busy||Date.now()<queueUntil;
 const p=data.progress;status.textContent=busy?`${run.status==='queued'?'等待執行':'更新中'}${p?.state==='running'&&p.total?` · ${p.completed} / ${p.total} 檔`:''}`:Date.now()<queueUntil?'更新已送出，等待 GitHub 建立工作…':run?.conclusion==='failure'?(p?.state==='quota_exhausted'?labels.quota_exhausted:'最近工作失敗，請開啟執行紀錄查看原因。'):['cancelled','timed_out','action_required'].includes(run?.conclusion)?'最近工作已中止或逾時，請查看執行紀錄。':(labels[p?.state]||'可以手動啟動更新。');
 if(p?.as_of&&!busy)status.textContent+=`\n行情日期：${p.as_of}`;
 if(run?.html_url){link.href=run.html_url;link.hidden=false;}
 }catch(e){authorized=false;button.disabled=true;status.textContent=e.message;}}
button.addEventListener('click',async()=>{if(!authorized||busy)return;button.disabled=true;try{await api('/api/admin/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});queueUntil=Date.now()+90000;status.textContent='已送出更新工作，等待執行…';setTimeout(poll,5000);}catch(e){status.textContent=e.message;button.disabled=false;}});
poll();setInterval(poll,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
