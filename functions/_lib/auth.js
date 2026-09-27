import {createRemoteJWKSet,jwtVerify} from 'jose';
const sets=new Map();
export class ApiError extends Error{constructor(status,message){super(message);this.status=status;}}
export async function authorize(request,env,keys){
 if(!env.ACCESS_ISSUER||!env.ACCESS_AUDIENCE||!env.ADMIN_EMAIL)throw new ApiError(503,'管理者登入尚未設定');
 const issuer=env.ACCESS_ISSUER.replace(/\/$/,'');
 if(!/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(issuer))throw new ApiError(503,'登入設定有誤');
 const token=request.headers.get('Cf-Access-Jwt-Assertion');
 if(!token)throw new ApiError(401,'請先使用管理者身分登入');
 try{
  if(!keys){if(!sets.has(issuer))sets.set(issuer,createRemoteJWKSet(new URL(issuer+'/cdn-cgi/access/certs')));keys=sets.get(issuer);}
  const {payload}=await jwtVerify(token,keys,{issuer,audience:env.ACCESS_AUDIENCE,algorithms:['RS256'],requiredClaims:['exp','iat','email']});
  if(typeof payload.email!=='string'||payload.email.toLowerCase()!==env.ADMIN_EMAIL.toLowerCase())throw new Error('email');
  return {email:payload.email};
 }catch{throw new ApiError(403,'管理者登入驗證失敗');}
}
