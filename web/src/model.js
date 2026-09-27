export const PERIODS={'1M':21,'3M':63,'6M':126,'12M':252};
export const TRAILS={'1M':4,'3M':13,'6M':26,'12M':52};
export const QUADRANTS={leading:'領先',weakening:'轉弱',lagging:'落後',improving:'改善'};
export const SECTORS={'10':'能源','15':'原物料','20':'工業','25':'非必需消費','30':'必需消費','35':'醫療保健','40':'金融','45':'資訊科技','50':'通訊服務','55':'公用事業','60':'房地產'};
export const COLORS={'10':'#daaa62','15':'#d0786b','20':'#adc0a5','25':'#bf9ee4','30':'#d6c183','35':'#65baa7','40':'#6c9cde','45':'#f2a65a','50':'#55aacf','55':'#a3a7cb','60':'#d29baa'};
export function formatPercent(n){return Number.isFinite(n)?`${n>0?'+':''}${(n*100).toFixed(1)}%`:'—';}
export function selectGroups(data,{level,minNames}){return data.groups.filter(g=>g.level===level&&g.valid_count>=minNames);}
export function sortGroups(groups,period,key='rs',direction=-1){
  return [...groups].sort((a,b)=>{
    const get=g=>key==='name'?g.name:key==='count'?g.valid_count:g.periods[key in PERIODS?key:period]?.[key in PERIODS?'rs':key];
    const av=get(a),bv=get(b);
    if(av==null)return bv==null?0:1;if(bv==null)return -1;
    return direction*(typeof av==='string'?av.localeCompare(bv):av-bv);
  });
}
export function relativeSeries(group,benchmark,days){
  if(benchmark.length<=days)return [];
  const b=benchmark.slice(-days-1), values=new Map(group.index.map(p=>[p.date,p.value]));
  if(b.some(p=>!Number.isFinite(values.get(p.date))))return [];
  const first=values.get(b[0].date);
  if(!Number.isFinite(first)||first<=0)return [];
  return b.map(p=>[p.date,Number.isFinite(values.get(p.date))?100*(values.get(p.date)/first)/(p.value/b[0].value):null]);
}
export function displayName(g){return g.level==='L1'?(SECTORS[g.code]||g.name):g.name;}
export function escapeHTML(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
