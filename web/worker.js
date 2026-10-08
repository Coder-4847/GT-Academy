import {loadPyodide} from './vendor/pyodide/pyodide.mjs';
let py,bridge;
// Cache the pinned runtime locally. A slow/blocked request must not hang forever.
const networkFetch=self.fetch.bind(self);
let downloaded=0,lastProgress=0;
self.fetch=async(input,init={})=>{
  const url=new URL(typeof input==='string'||input instanceof URL?String(input):input.url,import.meta.url);
  const runtime=url.pathname.includes('/vendor/pyodide/');
  let cache;
  if(runtime){try{cache=await caches.open('gt-academy-pyodide-0.27.7');const saved=await cache.match(url.href);if(saved)return saved;}catch{}}
  const response=await networkFetch(input,{...init,signal:init.signal||AbortSignal.timeout(45000)});
  if(!response.ok||!runtime||!response.body)return response;
  const reader=response.body.getReader();
  const stream=new ReadableStream({async pull(controller){
    try{const {done,value}=await reader.read();if(done){controller.close();return;}downloaded+=value.byteLength;
      if(performance.now()-lastProgress>200){lastProgress=performance.now();self.postMessage({status:`Downloading game files - ${(downloaded/1048576).toFixed(1)} MB received`});}
      controller.enqueue(value);
    }catch(error){controller.error(error);}
  },cancel(){reader.cancel();}});
  const result=new Response(stream,{status:response.status,headers:response.headers});
  if(cache)cache.put(url.href,result.clone()).catch(()=>{});
  return result;
};
const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
async function checked(url,expected){
  const response=await fetch(url); if(!response.ok)throw Error(`Could not load ${url} (${response.status}). Reload and try again.`);
  const bytes=await response.arrayBuffer(); if(expected&&await hash(bytes)!==expected)throw Error('Game file checksum mismatch. Reload to get the current version.');
  return bytes;
}
const ready=(async()=>{
  self.postMessage({status:'Loading game files...'});
  py=await loadPyodide({indexURL:new URL('./vendor/pyodide/',import.meta.url).href});
  await py.loadPackage('numpy');
  self.postMessage({status:'Opening circuits and cars...'});
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
