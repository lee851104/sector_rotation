import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPair,exportJWK,SignJWT,createLocalJWKSet} from 'jose';
import {authorize} from '../../functions/_lib/auth.js';
import {handleRefresh,handleStatus} from '../../functions/_lib/handlers.js';
const {privateKey,publicKey}=await generateKeyPair('RS256');
const jwk=await exportJWK(publicKey);jwk.kid='test';
const keys=createLocalJWKSet({keys:[jwk]});
const env={ACCESS_ISSUER:'https://test.cloudflareaccess.com',ACCESS_AUDIENCE:'test-aud',ADMIN_EMAIL:'owner@example.com',GITHUB_ACTIONS_TOKEN:'server-secret',GITHUB_REPOSITORY:'lee851104/sector_rotation',GITHUB_BRANCH:'main'};
async function token(opts={}){return new SignJWT({email:opts.email||env.ADMIN_EMAIL}).setProtectedHeader({alg:'RS256',kid:opts.kid||'test'}).setIssuer(opts.issuer||env.ACCESS_ISSUER).setAudience(opts.aud||env.ACCESS_AUDIENCE).setIssuedAt().setExpirationTime(opts.exp||'5m').sign(opts.key||privateKey);}
async function request(opts={}){return new Request('https://example.pages.dev/api/admin/refresh',{method:'POST',headers:{'Cf-Access-Jwt-Assertion':await token(opts),'Origin':opts.origin||'https://example.pages.dev','Content-Type':'application/json'},body:'{}'});}
test('signed authorized JWT is accepted',async()=>{assert.equal((await authorize(await request(),env,keys)).email,env.ADMIN_EMAIL);});
for(const [name,opts] of Object.entries({expired:{exp:1},audience:{aud:'other'},issuer:{issuer:'https://evil.example'},email:{email:'other@example.com'},unknownKey:{kid:'unknown'}})){
 test(`rejects ${name} JWT`,async()=>{await assert.rejects(async()=>authorize(await request(opts),env,keys));});
}
test('forged signature and trusted email header do not authorize',async()=>{
 const attacker=await generateKeyPair('RS256');
 await assert.rejects(async()=>authorize(await request({key:attacker.privateKey}),env,keys));
 await assert.rejects(()=>authorize(new Request('https://example.pages.dev/api/admin/status',{headers:{'Cf-Access-Authenticated-User-Email':env.ADMIN_EMAIL}}),env,keys));
});
test('missing configuration fails closed',async()=>{assert.equal((await handleRefresh(await request(),{}, {keys})).status,503);});
test('cross origin rejected before GitHub call',async()=>{
 const r=await handleRefresh(await request({origin:'https://attacker.example'}),env,{keys,fetcher:()=>{throw new Error('must not call')}});
 assert.equal(r.status,403);
});
test('active run returned without a second dispatch',async()=>{
 const fetcher=async(url,opts)=>{
  assert.equal(opts.method||'GET','GET');
  return Response.json({workflow_runs:[{id:7,status:'in_progress',html_url:'https://github.com/lee851104/sector_rotation/actions/runs/7',head_branch:'main'}]});
 };
 const r=await handleRefresh(await request(),env,{keys,fetcher});
 assert.equal(r.status,202);assert.equal((await r.json()).run.id,7);
});
test('GitHub errors are not reported as success or leaked',async()=>{
 const r=await handleRefresh(await request(),env,{keys,fetcher:async()=>new Response('server-secret',{status:403})});
 assert.equal(r.status,502);assert.ok(!(await r.text()).includes('server-secret'));
});
test('dispatch only uses server-side repo workflow and branch',async()=>{
 let posted=false;
 const fetcher=async(url,opts={})=>{
  if(opts.method==='POST'){assert.match(url,/update-deploy.yml\/dispatches$/);assert.deepEqual(JSON.parse(opts.body),{ref:'main',inputs:{mode:'update'}});posted=true;return new Response(null,{status:204});}
  return Response.json({workflow_runs:[]});
 };
 const r=await handleRefresh(await request(),env,{keys,fetcher});assert.equal(r.status,202);assert.equal(posted,true);
});
