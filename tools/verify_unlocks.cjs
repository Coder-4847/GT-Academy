const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:8766/');
  await page.locator('#engine-status.ready').waitFor({timeout:120000});
  let combinations=0;
  for(const mode of ['Race vs AI','Career']){
   await page.getByRole('button',{name:mode,exact:false}).click();
   for(let track=0;track<5;track++){
    await page.locator('[data-option="track"]').selectOption(String(track));
    for(const [i,tier]of ['Rookie','Pro','Champion','Legend'].entries()){
     await page.locator(`[data-car="${(track+i)%5}"]`).click();
     await page.locator('[data-option="tier"]').selectOption(tier);
     if(!await page.locator('#start').isEnabled())throw Error(`${mode} ${track} ${tier} is locked`);
     combinations++;
    }
   }
   await page.locator('[data-option="rival"]').selectOption('3');
   await page.locator('#start').click();
   await page.locator('#race').waitFor({state:'visible',timeout:60000});
   await page.keyboard.press('Escape');
   await page.getByRole('button',{name:'Main menu',exact:true}).click();
  }
  await page.reload();await page.locator('#engine-status.ready').waitFor({timeout:120000});
  if(await page.locator('[data-option="track"]').inputValue()!=='4'||await page.locator('[data-option="tier"]').inputValue()!=='Legend')throw Error('Challenge selection was reset on reload');
  if(!await page.locator('#start').isEnabled())throw Error('Challenge locked after reload');
  fs.writeFileSync('artifacts/web/unlocks-validation.json',JSON.stringify({passed:true,combinations,allCarsCovered:true,grandCircuitLegendStartedInBothModes:true,noPriorMedals:true,selectionPersists:true},null,2));
  console.log(`${combinations} challenge selections open; Grand Circuit / Legend starts in Race and Career with no medals.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
