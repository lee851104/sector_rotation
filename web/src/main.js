import {PERIODS,QUADRANTS,COLORS,displayName,formatPercent,selectGroups,sortGroups,escapeHTML as esc} from './model.js';
import {renderRotation,renderRelative} from './charts.js';
let data;let state={level:'L1',period:'1M',minNames:2,path:'tails',sort:'1M',direction:-1};let selected=new Set();
const $=id=>document.getElementById(id),cls=v=>v>0?'up':v<0?'down':'';
function message(text,good=false){$('notice').classList.toggle('good',good);$('notice').replaceChildren(Object.assign(document.createElement('span'),{textContent:text}));}
function resetSelection(){const gs=sortGroups(selectGroups(data,state),state.period).filter(g=>g.periods[state.period]?.rs!=null);selected=new Set([...gs.slice(0,3),...gs.slice(-3)].map(g=>g.id));}
function cards(id,groups){$(''+id).classList.remove('empty');$(id).innerHTML=groups.length?groups.map(g=>{const m=g.periods[state.period];return `<article class="strength-row"><div class="strength-title"><strong>${esc(displayName(g))}</strong><small>${g.valid_count} 家</small><span class="return ${cls(m.rs)}">${formatPercent(m.rs)} <small>RS</small></span></div><div class="stock-chips">${m.stocks.slice(0,8).map(s=>`<span class="stock-chip">${esc(s.symbol)}<span class="${cls(s.return)}">${formatPercent(s.return)}</span></span>`).join('')}</div></article>`;}).join(''):'<p class="empty">此篩選條件沒有足夠資料。</p>';}
function render(){
 if(!data)return;const groups=selectGroups(data,state),ranked=sortGroups(groups,state.period).filter(g=>g.periods[state.period]?.rs!=null),best=ranked[0];
 $('stat-period').textContent=state.period;$('stat-leading').innerHTML=`${groups.filter(g=>g.rotation.at(-1)?.quadrant==='leading').length} <i>個產業</i>`;
 $('stat-best').textContent=best?displayName(best):'—';$('stat-best-rs').textContent=`相對報酬 ${formatPercent(best?.periods[state.period]?.rs)}`;
 $('stat-best-rs').className=cls(best?.periods[state.period]?.rs);
 $('rotation-count').textContent=`${groups.length} GROUPS`;$('table-count').textContent=`${groups.length} 個分組 · 點選產業加入比較`;
 cards('strongest',ranked.slice(0,3));cards('weakest',[...ranked].reverse().slice(0,3));
 $('chart-legend').innerHTML=groups.filter(g=>selected.has(g.id)).map(g=>`<span><i style="background:${COLORS[g.sector_code]||'#aaa'}"></i>${esc(displayName(g))}</span>`).join('')||'<span>從下方排名表選取產業</span>';
 $('ranking-body').innerHTML=sortGroups(groups,state.period,state.sort,state.direction).map(g=>{const m=g.periods[state.period],q=g.rotation.at(-1)?.quadrant;return `<tr class="${selected.has(g.id)?'selected':''}"><td><button class="row-name" data-group="${esc(g.id)}" aria-pressed="${selected.has(g.id)}"><strong><span style="background:${COLORS[g.sector_code]||'#aaa'}"></span>${esc(displayName(g))}</strong><small>${esc(g.code)} · ${esc(g.name)}</small></button></td><td>${g.valid_count} <span class="caption">/ ${g.member_count}</span></td>${Object.keys(PERIODS).map(p=>`<td class="${cls(g.periods[p]?.rs)}">${formatPercent(g.periods[p]?.rs)}</td>`).join('')}<td title="有效個股 ${m.breadth_count} 家"><span class="breadth-meter"><i style="width:${(m.breadth||0)*100}%"></i></span>${m.breadth==null?'—':`${Math.round(m.breadth*100)}%`}</td><td><span class="quadrant ${q||''}">${QUADRANTS[q]||'資料不足'}</span></td></tr>`;}).join('')||'<tr><td colspan="8" class="empty-cell">此篩選条件沒有分組。</td></tr>';
 renderRotation(groups,state.period,state.path,selected);renderRelative(groups,data.benchmark_series,state.period,selected);
}
$('level').addEventListener('change',e=>{state.level=e.target.value;if(data){resetSelection();render();}});
$('min-names').addEventListener('change',e=>{state.minNames=Math.max(1,Number(e.target.value)||1);if(data){resetSelection();render();}});
$('path-mode').addEventListener('change',e=>{state.path=e.target.value;render();});
$('periods').addEventListener('click',e=>{const p=e.target.dataset.period;if(!p)return;state.period=p;state.sort=p;document.querySelectorAll('[data-period]').forEach(b=>{b.classList.toggle('active',b.dataset.period===p);b.setAttribute('aria-pressed',b.dataset.period===p);});if(data){resetSelection();render();}});
document.querySelector('thead').addEventListener('click',e=>{const key=e.target.dataset.sort;if(!key)return;state.direction=state.sort===key?-state.direction:-1;state.sort=key;render();});
$('ranking-body').addEventListener('click',e=>{const b=e.target.closest('[data-group]');if(!b)return;selected.has(b.dataset.group)?selected.delete(b.dataset.group):selected.add(b.dataset.group);render();});
async function load(){try{const response=await fetch('/data/dashboard.json',{cache:'no-store'});if(!response.ok)throw new Error('uninitialized');const value=await response.json();if(value.schema_version!==1||!Array.isArray(value.groups)||!Array.isArray(value.benchmark_series))throw new Error('invalid');data=value;
 $('market-date').textContent=`行情 ${data.as_of}`;$('stat-date').textContent=data.as_of;$('updated').textContent=`更新 ${new Date(data.updated_at).toLocaleString('zh-TW',{hour12:false})}`;
 $('stat-coverage').innerHTML=`${data.coverage.valid} <i>/ ${data.coverage.total}</i>`;$('coverage-detail').textContent=`行情覆蓋 ${(data.coverage.prices*100).toFixed(1)}% · L4 分類 ${(data.coverage.classification.L4*100).toFixed(1)}%`;
 $('missing-detail').textContent=data.missing_symbols.length?` 缺漏股票：${data.missing_symbols.join('、')}`:'';document.querySelector('.live-dot').classList.add('ready');
 const age=(Date.now()-Date.parse(`${data.as_of}T23:59:59Z`))/86400000;
 message(age>4?`目前顯示 ${data.as_of} 的行情；已超過四天未成功更新，請查看管理頁。`:`資料日期 ${data.as_of} · 以目前成分股及分類回看。最新資料會在下一次成功更新後顯示。`,age<=4);
 resetSelection();render();
 }catch{message('尚未完成首次行情更新。此頁不使用模擬數據；管理者完成資料連線並執行更新後，即可查看分析。');renderRotation([],'1M','tails',selected);renderRelative([],[],'1M',selected);}}
load();
