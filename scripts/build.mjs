import {copyFile,mkdir,readFile,writeFile} from 'node:fs/promises';
const source=process.env.GICS_DATASET||'data/state/dashboard.json';
try{const d=JSON.parse(await readFile(source,'utf8'));if(d.schema_version!==1||!d.as_of||!Array.isArray(d.groups))throw new Error('Invalid dataset');await mkdir('dist/data',{recursive:true});await copyFile(source,'dist/data/dashboard.json');console.log(`Real dataset included: ${d.as_of}`);}catch(e){if(e.code!=='ENOENT')throw e;console.log('No dataset yet; dashboard will display the uninitialized state.');}
await writeFile('dist/_routes.json',JSON.stringify({version:1,include:['/api/admin/*'],exclude:[]}));
await writeFile('dist/_headers',`/data/*\n  Cache-Control: no-cache, must-revalidate\n/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: same-origin\n  X-Frame-Options: DENY\n`);
