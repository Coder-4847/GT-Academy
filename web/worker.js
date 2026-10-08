import {loadPyodide} from './vendor/pyodide/pyodide.mjs';
let py,bridge;
const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
async function checked(url,expected){
  const response=await fetch(url); if(!response.ok)throw Error(`Could not load ${url} (${response.status}). Reload and try again.`);
  const bytes=await response.arrayBuffer(); if(expected&&await hash(bytes)!==expected)throw Error('Game file checksum mismatch. Reload to get the current version.');
  return bytes;
}
const ready=(async()=>{
  self.postMessage({status:'Loading driving engine…'});
  py=await loadPyodide({indexURL:new URL('./vendor/pyodide/',import.meta.url).href});
  await py.loadPackage('numpy');
  const catalog=await (await fetch('./catalog.json')).json();
  const bytes=await checked('./simulation.zip',catalog.simulation_sha256);
  py.unpackArchive(bytes,'zip');
  py.FS.writeFile('bridge.py',new Uint8Array(await checked('./bridge.py')));
  py.runPython('import bridge'); bridge=py.globals.get('bridge').game;
  const version=py.runPython('bridge.SIM_VERSION');
  if(version!==catalog.sim_version)throw Error('Simulation version mismatch. Refusing to run incompatible game files.');
  self.postMessage({status:'Ready to drive',ready:true,version});
})();
ready.catch(error=>self.postMessage({fatal:error.message}));
self.onmessage=async({data})=>{
  try{
    await ready;
    let result;
    if(data.type==='start'){
      if(data.model)py.FS.writeFile('/opponent.npz',new Uint8Array(await checked(data.model.file,data.model.sha256)));
      result=bridge.start(JSON.stringify(data.options),data.profile||'{}');
    }else if(data.type==='step')result=bridge.step(data.steer,data.pedal,data.ticks,data.assist);
    else if(data.type==='reset')result=bridge.reset();
    self.postMessage({id:data.id,result:JSON.parse(result)});
  }catch(error){self.postMessage({id:data.id,error:error.message});}
};
