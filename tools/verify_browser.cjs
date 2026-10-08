// End-to-end checks against the same static files served by GitHub Pages.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')console.log('Browser:',m.text());});
 try{
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.getByRole('heading',{name:'Find your next tenth.'}).waitFor();
  await page.locator('#engine-status.ready').waitFor({timeout:120000});
  await page.screenshot({path:'artifacts/web/home.png',fullPage:true});
  await page.getByRole('button',{name:'Garage',exact:true}).click();
  await page.getByRole('button',{name:'Drive Comet'}).click();
  await page.getByRole('button',{name:'Circuits',exact:true}).click();
  await page.locator('[data-pick-track="4"]').click();
  await page.getByRole('button',{name:'Free Practice',exact:false}).click();
  await page.getByRole('button',{name:'Start driving'}).click();
  await page.locator('#race').waitFor({state:'visible',timeout:30000});
  await page.keyboard.down('ArrowUp');await page.waitForTimeout(2500);await page.keyboard.up('ArrowUp');
  if(!/KM\/H/.test(await page.locator('#hud').innerText()))throw Error('HUD did not update');
  await page.screenshot({path:'artifacts/web/race.png'});
  await page.keyboard.press('Escape');await page.getByRole('heading',{name:'Paused.'}).waitFor();
  await page.getByRole('button',{name:'Main menu',exact:true}).click();
  await page.locator('[data-option="track"]').selectOption('0');
  await page.getByRole('button',{name:'Race vs AI',exact:false}).click();
  await page.locator('[data-option="rival"]').selectOption('3');
  await page.getByRole('button',{name:'Start driving'}).click();
  await page.locator('#race').waitFor({state:'visible',timeout:30000});
  await page.waitForTimeout(5000);
  if(!/POSITION/.test(await page.locator('#hud').innerText()))throw Error('AI race HUD missing');
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Main menu',exact:true}).click();
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.locator('[data-option="mute"]').check();
  await page.reload();await page.locator('#engine-status.ready').waitFor({timeout:120000});
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  if(!await page.locator('[data-option="mute"]').isChecked())throw Error('Settings did not survive reload');
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Drive',exact:true}).click();
  await page.screenshot({path:'artifacts/web/mobile.png',fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile horizontal overflow');
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync('artifacts/web/browser-validation.json',JSON.stringify({passed:true,checks:['runtime startup','car and track selection','practice driving','pause and resume menu','trained AI race','persistent settings','mobile layout'],errors},null,2));
  console.log('Browser checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
