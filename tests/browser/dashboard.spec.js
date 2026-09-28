import {test,expect} from '@playwright/test';

// Synthetic values exist only in intercepted test responses, never in site assets.
function fixture(){
 const dates=Array.from({length:300},(_,i)=>new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10));
 const groups=['45','50','35','10','40','55','60','20','15','25','30'].flatMap((code,i)=>['L1','L2','L3','L4'].map((level,j)=>({id:`${level}:${code}`,level,code,sector_code:code,name:['Information Technology','Communication Services','Health Care','Energy','Financials','Utilities','Real Estate','Industrials','Materials','Consumer Discretionary','Consumer Staples'][i],member_count:10,valid_count:10,
 periods:Object.fromEntries(['1M','3M','6M','12M'].map(p=>[p,{return:.1-i*.02,rs:.08-i*.016,breadth:.8-i*.05,breadth_count:10,stocks:[{symbol:'TEST',name:'Testing only',return:.12}]}])),
 index:dates.map((date,k)=>({date,value:100+k*(.1-i*.012),count:10})),rotation:Array.from({length:52},(_,k)=>({date:dates[k*5],x:99+i*.3+k*.01,y:101-i*.2-k*.008,quadrant:i<3?'leading':i<6?'weakening':i<9?'lagging':'improving'}))})));
 return {schema_version:1,as_of:dates.at(-1),updated_at:new Date().toISOString(),source:'TEST FIXTURE',benchmark:'SPY',coverage:{valid:110,total:110,prices:1,classification:{L1:1,L2:1,L3:1,L4:1}},missing_symbols:[],groups,benchmark_series:dates.map(date=>({date,value:100}))};
}
test('honest empty state without fake quotes',async({page})=>{
 await page.route('**/data/dashboard.json',r=>r.fulfill({status:404,body:''}));await page.goto('/');
 await expect(page.getByRole('status')).toContainText('不使用模擬數據');
 await expect(page.locator('#stat-date')).toHaveText('—');
 await page.screenshot({path:'reports/figures/dashboard-empty.png',fullPage:true});
});
test('desktop controls, sorting and charts use dataset',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/data/dashboard.json',r=>r.fulfill({json:fixture()}));await page.setViewportSize({width:1440,height:1100});await page.goto('/');
 await expect(page.locator('#ranking-body tr')).toHaveCount(11);
 await expect(page.locator('#relative-chart canvas')).toHaveCount(1);
 await page.getByRole('button',{name:'3M',exact:true}).click();await expect(page.locator('#stat-period')).toHaveText('3M');
 await page.locator('#level').selectOption('L4');await expect(page.locator('#ranking-body tr')).toHaveCount(11);
 await page.locator('#min-names').fill('20');await page.locator('#min-names').dispatchEvent('change');await expect(page.locator('#ranking-body')).toContainText('沒有分組');
 await page.locator('#min-names').fill('2');await page.locator('#min-names').dispatchEvent('change');await page.locator('#level').selectOption('L1');
 const first=page.locator('[data-group]').first();const before=await first.getAttribute('aria-pressed');await first.click();expect(await first.getAttribute('aria-pressed')).not.toBe(before);
 await page.locator('#path-mode').selectOption('arrows');await page.locator('#rotation-chart').hover();
 await page.getByRole('button',{name:'RS 1M ↕'}).click();await page.waitForTimeout(450);
 expect(errors).toEqual([]);await page.screenshot({path:'reports/figures/dashboard-test-data.png',fullPage:true});
});
test('mobile layout does not overflow the viewport',async({page})=>{
 await page.route('**/data/dashboard.json',r=>r.fulfill({json:fixture()}));await page.setViewportSize({width:390,height:844});await page.goto('/');
 await expect(page.locator('#ranking-body tr')).toHaveCount(11);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
 await page.screenshot({path:'reports/figures/dashboard-mobile-test-data.png',fullPage:true});
});
test('admin fails closed when configuration is missing',async({page})=>{
 await page.route('**/api/admin/status',r=>r.fulfill({status:503,json:{error:'管理者登入尚未設定'}}));await page.goto('/admin/');
 await expect(page.locator('#refresh')).toBeHidden();await expect(page.getByRole('status')).toContainText('GitHub');
 await expect(page.getByRole('link',{name:'在 GitHub 手動更新 ↗'})).toHaveAttribute('href','https://github.com/lee851104/sector_rotation/actions/workflows/update-deploy.yml');
});
