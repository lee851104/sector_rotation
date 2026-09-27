import {authorize,ApiError} from './auth.js';
import {github} from './github.js';
const active=r=>['queued','in_progress','waiting','pending','requested'].includes(r.status);
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
function failure(error){return json({error:error instanceof ApiError?error.message:'更新服務發生錯誤'},error instanceof ApiError?error.status:500);}
export async function handleRefresh(request,env,deps={}){
 try{
  if(request.method!=='POST')throw new ApiError(405,'只接受 POST');
  await authorize(request,env,deps.keys);
  if(request.headers.get('Origin')!==new URL(request.url).origin)throw new ApiError(403,'不接受跨網站操作');
  if(!request.headers.get('Content-Type')?.startsWith('application/json'))throw new ApiError(415,'需要 JSON 請求');
  const api=github(env,deps.fetcher);const running=(await api.runs()).find(active);
  if(running)return json({state:'running',run:running},202);
  await api.dispatch();return json({state:'queued',message:'更新已排入佇列，請稍候。'},202);
 }catch(error){return failure(error);}
}
export async function handleStatus(request,env,deps={}){
 try{
  await authorize(request,env,deps.keys);
  const api=github(env,deps.fetcher);const runs=await api.runs();
  return json({run:runs.find(active)||runs[0]||null,progress:await api.progress()});
 }catch(error){return failure(error);}
}
