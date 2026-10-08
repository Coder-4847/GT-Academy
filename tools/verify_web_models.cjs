// Run exported policies inside the actual browser Python/NumPy runtime.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage();const results=[];
 try{
  await page.goto(process.env.TEST_URL||'http://127.0.0.1:8766/',{waitUntil:'domcontentloaded'});
  await page.exposeFunction('reportModel',row=>{results.push(row);fs.writeFileSync('artifacts/web/wasm-races.json',JSON.stringify(results,null,2));console.log(`${row.key}: ${row.laps.length}/5 ${row.dnf||''}`);});
  await page.evaluate(async()=>{
   const catalog=await(await fetch('./catalog.json')).json();
   const all=Object.entries(catalog.models);
   const base=location.href;
   const source=`import {loadPyodide} from '${base}vendor/pyodide/pyodide.mjs';
   self.onmessage=async({data})=>{try{
    const py=await loadPyodide({indexURL:'${base}vendor/pyodide/'});await py.loadPackage('numpy');
    py.unpackArchive(await(await fetch('${base}simulation.zip')).arrayBuffer(),'zip');
    py.FS.writeFile('bridge.py',new Uint8Array(await(await fetch('${base}bridge.py')).arrayBuffer()));
    py.runPython('from bridge import NumpyDriver; from gt_academy.game.racing import Opponent; import json');
    for(const [key,model]of data){
     py.FS.writeFile('/check.npz',new Uint8Array(await(await fetch('${base}'+model.file)).arrayBuffer()));
     const [track,car]=key.split(':').map(Number);py.globals.set('car',car);py.globals.set('track',track);
     const row=JSON.parse(py.runPython("driver=NumpyDriver('/check.npz',car,track)\\nopponent=Opponent(driver,car,track,5)\\nwhile opponent.finish_time is None and not opponent.dnf: opponent.step()\\njson.dumps(dict(laps=opponent.sim.lap.lap_times,dnf=opponent.dnf,finish=opponent.finish_time))"));
     self.postMessage({row:{key,...row}});
    }self.postMessage({done:true});
   }catch(e){self.postMessage({error:e.message});}}`;
   const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
   await Promise.all([0,1,2,3].map(i=>new Promise((resolve,reject)=>{const w=new Worker(url,{type:'module'});w.onmessage=async({data})=>{if(data.row)await window.reportModel(data.row);if(data.done){w.terminate();resolve();}if(data.error){w.terminate();reject(Error(data.error));}};w.onerror=e=>reject(Error(e.message));w.postMessage(all.filter((_,n)=>n%4===i));})));
  });
  const failed=results.filter(r=>r.laps.length!==5);console.log(`${results.length-failed.length}/${results.length} browser policies passed five laps.`);
  if(failed.length)process.exitCode=2;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
