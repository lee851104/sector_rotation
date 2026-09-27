import {ApiError} from './auth.js';
export function github(env,fetcher=fetch){
 if(!env.GITHUB_ACTIONS_TOKEN)throw new ApiError(503,'更新服務尚未設定');
 const repo=env.GITHUB_REPOSITORY||'lee851104/sector_rotation';
 if(!/^[\w.-]+\/[\w.-]+$/.test(repo))throw new ApiError(503,'儲存庫設定有誤');
 const branch=env.GITHUB_BRANCH||'main';
 const base=`https://api.github.com/repos/${repo}`;
 async function call(path,options={}){
  let r;try{r=await fetcher(base+path,{...options,headers:{'Authorization':`Bearer ${env.GITHUB_ACTIONS_TOKEN}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'gics-dashboard','Content-Type':'application/json'},signal:AbortSignal.timeout(15000)});}catch{throw new ApiError(502,'無法連線 GitHub，請稍後再試');}
  if(!r.ok)throw new ApiError(502,'GitHub 拒絕操作，請檢查工作流程與權限');
  return r.status===204?null:r.json();
 }
 function cleanRun(run){return {id:run.id,status:run.status,conclusion:run.conclusion||null,created_at:run.created_at||null,html_url:`https://github.com/${repo}/actions/runs/${Number(run.id)}`};}
 return {
  async runs(){const body=await call(`/actions/workflows/update-deploy.yml/runs?branch=${encodeURIComponent(branch)}&per_page=10`);return (body.workflow_runs||[]).map(cleanRun);},
  async dispatch(){return call('/actions/workflows/update-deploy.yml/dispatches',{method:'POST',body:JSON.stringify({ref:branch,inputs:{mode:'update'}})});},
  async progress(){try{const item=await call('/contents/status.json?ref=data-state');const text=atob(item.content.replace(/\s/g,''));const p=JSON.parse(text);return {state:p.state,completed:p.completed,total:p.total,failed:p.failed,as_of:p.as_of,updated_at:p.updated_at};}catch{return null;}},
 };
}
