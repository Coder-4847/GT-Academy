const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext();const page=await context.newPage();
  let release;const hold=new Promise(resolve=>release=resolve);
  await context.route('**/pyodide.asm.wasm',async route=>{await hold;await route.continue();});
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:8766/');
  await page.getByRole('button',{name:'Free Practice',exact:false}).click();
  const start=page.getByRole('button',{name:'Start driving'});
  if(!await start.isEnabled())throw Error('Play is disabled during download');
  await start.click();await page.getByRole('heading',{name:'Loading your drive.'}).waitFor();
  await page.getByRole('button',{name:'Back to menu',exact:true}).click();
  await start.click();release();
  await page.locator('#race').waitFor({state:'visible',timeout:60000});
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Main menu',exact:true}).click();
  await page.reload();await page.locator('#engine-status.ready').waitFor({timeout:60000});
  const cached=await page.evaluate(async()=>{const c=await caches.open('gt-academy-pyodide-0.27.7');return(await c.keys()).map(x=>x.url);});
  if(!cached.some(x=>x.endsWith('pyodide.asm.wasm')))throw Error('Runtime was not cached');
  await context.close();
  const failed=await browser.newContext();const errorPage=await failed.newPage();errorPage.on('console',m=>{if(m.type()==='error')console.log(m.text());});
  await failed.route('**/worker.js*',route=>route.abort('failed'));
  await errorPage.goto(process.env.TEST_URL||'http://127.0.0.1:8766/');
  await errorPage.getByRole('button',{name:'Start driving'}).click();
  await errorPage.getByRole('button',{name:'Retry loading'}).waitFor({timeout:30000});
  await failed.unroute('**/worker.js*');
  await errorPage.getByRole('button',{name:'Retry loading'}).click();
  await errorPage.locator('#race').waitFor({state:'visible',timeout:60000});
  fs.writeFileSync('artifacts/web/loading-validation.json',JSON.stringify({passed:true,checks:['Play enabled during delayed download','Loading progress shown','Cancel and restart safe','Runtime cached','Network failure shows retry','Retry recovers without page reload']},null,2));
  console.log('Slow download, cache, cancel, network failure and retry checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
