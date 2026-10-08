const lerp=(a,b,t)=>a+(b-a)*t;
export function pose(a,b,t){if(!a)return b; const s={...b}; for(const k of ['x','y','vx','vy','steering'])s[k]=lerp(a[k],b[k],t);s.heading=a.heading+Math.atan2(Math.sin(b.heading-a.heading),Math.cos(b.heading-a.heading))*t;return s;}
export function carSVG(car){const c=`rgb(${car.color})`;return `<svg viewBox="0 0 180 80" aria-hidden="true"><ellipse cx="88" cy="64" rx="61" ry="6" fill="#24372c15"/><path d="M25 42L40 36 62 17Q67 13 76 13H111L136 35 156 41 162 56H23Z" fill="${c}"/><path d="M66 19H79V35H47ZM85 19H109L128 35H85Z" fill="#29423f"/><path d="M27 45H151" stroke="#fff" stroke-opacity=".3"/><path d="M150 43H160V48H151Z" fill="#f9ebbe"/><path d="M23 42H30V48H23Z" fill="#a6533c"/><g fill="#263430"><circle cx="50" cy="55" r="12"/><circle cx="135" cy="55" r="12"/></g><g fill="#acb5a6" stroke="#33453b" stroke-width="3"><circle cx="50" cy="55" r="7"/><circle cx="135" cy="55" r="7"/></g></svg>`;}
export function trackSVG(track){const xs=track.center.map(p=>p[0]),ys=track.center.map(p=>p[1]),minX=Math.min(...xs),maxY=Math.max(...ys),w=Math.max(...xs)-minX,h=maxY-Math.min(...ys);return `<svg viewBox="${minX-35} ${-maxY-35} ${w+70} ${h+70}" aria-hidden="true"><path d="${track.center.map((p,i)=>(i?'L':'M')+p[0]+','+(-p[1])).join(' ')}Z" fill="none" stroke="#527560" stroke-width="${track.width}" stroke-linejoin="round"/><path d="M${track.center[0][0]},${-track.center[0][1]}h1" stroke="#b75335" stroke-width="${track.width*1.4}"/></svg>`;}
export class Renderer{
 constructor(canvas){this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false});this.camera=null;this.zoom=7;this.trails=[];this.lastTick=-1;}
 setTrack(track){this.track=track;this.path=new Path2D();track.center.forEach((p,i)=>i?this.path.lineTo(...p):this.path.moveTo(...p));this.path.closePath();this.camera=null;this.trails=[];
  this.trees=[];const xs=track.center.map(p=>p[0]),ys=track.center.map(p=>p[1]);this.bounds=[Math.min(...xs)-65,Math.min(...ys)-65,Math.max(...xs)+65,Math.max(...ys)+65];let seed=92;
  const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  for(let i=0;i<350;i++){const x=lerp(this.bounds[0],this.bounds[2],random()),y=lerp(this.bounds[1],this.bounds[3],random());if(track.center.every((p,j)=>j%3||Math.hypot(p[0]-x,p[1]-y)>track.width/2+13))this.trees.push([x,y,2+random()*3]);}}
 resize(quality='High'){const dpr=Math.min(quality==='High'?2:1,devicePixelRatio||1),w=Math.round(this.canvas.clientWidth*dpr),h=Math.round(this.canvas.clientHeight*dpr);if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}this.dpr=dpr;return [w/dpr,h/dpr];}
 road(ctx,zoom){const t=this.track;
  ctx.lineJoin='round';ctx.lineCap='round';ctx.strokeStyle='#a3ab9290';ctx.lineWidth=t.width+20;ctx.stroke(this.path);
  ctx.strokeStyle='#b3ae96';ctx.lineWidth=t.width+10;ctx.stroke(this.path);
  ctx.strokeStyle='#ddd9c7';ctx.lineWidth=t.width+1.2;ctx.stroke(this.path);
  ctx.strokeStyle='#47534f';ctx.lineWidth=t.width;ctx.stroke(this.path);
  ctx.strokeStyle='#e2dcc7';ctx.lineWidth=.3;ctx.setLineDash([2,9]);ctx.stroke(this.path);ctx.setLineDash([]);
  const p=t.center[0],q=t.center[2],angle=Math.atan2(q[1]-p[1],q[0]-p[0]);ctx.save();ctx.translate(...p);ctx.rotate(angle);
  for(let a=0;a<2;a++)for(let b=0;b<Math.ceil(t.width);b++){ctx.fillStyle=(a+b)%2?'#273b33':'#e9e4d4';ctx.fillRect(a-.5,b-t.width/2,1,1);}ctx.restore();
  for(const [x,y,r] of this.trees){ctx.fillStyle='#27463523';ctx.beginPath();ctx.ellipse(x+1,y-1,r*1.2,r,0,0,7);ctx.fill();ctx.fillStyle='#7c9374';ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fill();ctx.fillStyle='#91a284';ctx.beginPath();ctx.arc(x-r*.25,y+r*.25,r*.6,0,7);ctx.fill();}
 }
 car(ctx,s,car,ghost=false,rival=false){if(!s)return;ctx.save();ctx.translate(s.x,s.y);ctx.rotate(s.heading);ctx.globalAlpha=ghost?.4:1;ctx.fillStyle='#0b231b40';ctx.beginPath();ctx.roundRect(-2.1,-1.2,4.4,2.2,.5);ctx.fill();
  for(const x of [-1.35,1.15])for(const y of [-.95,.95]){ctx.save();ctx.translate(x,y);if(x>0)ctx.rotate(s.steering||0);ctx.fillStyle='#182b25';ctx.fillRect(-.4,-.19,.8,.38);ctx.restore();}
  ctx.fillStyle=`rgb(${car.color})`;ctx.beginPath();ctx.roundRect(-2,-.83,4.1,1.66,.45);ctx.fill();ctx.fillStyle='#edf0dc';ctx.fillRect(.8,-.14,1.1,.28);ctx.fillStyle='#24403d';ctx.fillRect(.35,-.68,.5,1.36);ctx.fillRect(-1.3,-.6,.4,1.2);ctx.fillStyle='#ffffff30';ctx.fillRect(-.75,-.65,1,.15);
  ctx.fillStyle='#f7e7b4';ctx.fillRect(1.9,-.65,.14,.3);ctx.fillRect(1.9,.35,.14,.3);ctx.fillStyle=s.brake>.1?'#ff7050':'#923d32';ctx.fillRect(-2,-.65,.12,.3);ctx.fillRect(-2,.35,.12,.3);
  if(rival){ctx.strokeStyle='#b5dbdc';ctx.lineWidth=.1;ctx.beginPath();ctx.arc(0,0,2.8,0,7);ctx.stroke();}ctx.restore();}
 draw(snapshot,cars,options,dt,{preview=false,clean=false}={}){if(!this.track)return;const [w,h]=this.resize(options.quality),ctx=this.ctx,d=this.dpr;ctx.setTransform(d,0,0,d,0,0);ctx.fillStyle='#c1c7b2';ctx.fillRect(0,0,w,h);
  let s=snapshot?.state;
  if(preview){const b=this.bounds;this.camera=[(b[0]+b[2])/2,(b[1]+b[3])/2];this.zoom=Math.min(w/(b[2]-b[0]),(h-50)/(b[3]-b[1]));}
  else if(s){if(!this.camera)this.camera=[s.x,s.y];const f=1-Math.exp(-5*dt);this.camera[0]=lerp(this.camera[0],s.x+Math.cos(s.heading)*s.vx*.35,f);this.camera[1]=lerp(this.camera[1],s.y+Math.sin(s.heading)*s.vx*.35,f);this.zoom=lerp(this.zoom,(w<700?7:9)/(1+Math.abs(s.vx)/170),1-Math.exp(-3*dt));}
  if(!this.camera)return;ctx.save();ctx.translate(w/2,h/2+(preview?24:0));ctx.scale(this.zoom,-this.zoom);ctx.translate(-this.camera[0],-this.camera[1]);this.road(ctx,this.zoom);
  if(s&&!preview){if(s.ticks!==this.lastTick&&Math.max(Math.abs(s.slip_front),Math.abs(s.slip_rear))>.18){this.trails.push([s.x,s.y,s.heading]);if(this.trails.length>450)this.trails.shift();}this.lastTick=s.ticks;
   ctx.strokeStyle='#263a2d60';ctx.lineWidth=.17;for(const [x,y,a]of this.trails){ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-Math.cos(a)*1.4,y-Math.sin(a)*1.4);ctx.stroke();}
   this.car(ctx,snapshot.ghost,cars[options.car],true);if(snapshot.opponent)this.car(ctx,snapshot.opponent,cars[options.rival],options.mode==='Time Trial',true);this.car(ctx,s,cars[options.car]);
  }else if(preview){const n=this.track.center.length,i=Math.floor(performance.now()/70)%n,p=this.track.center[i],q=this.track.center[(i+2)%n];this.car(ctx,{x:p[0],y:p[1],heading:Math.atan2(q[1]-p[1],q[0]-p[0]),steering:0},cars[options.car]);}ctx.restore();
  if(s&&!preview&&!clean){const b=this.bounds,scale=130/Math.max(b[2]-b[0],b[3]-b[1]);ctx.save();ctx.translate(w-95,h-105);ctx.fillStyle='#16332bc9';ctx.beginPath();ctx.roundRect(-78,-78,156,156,10);ctx.fill();ctx.scale(scale,-scale);ctx.translate(-(b[0]+b[2])/2,-(b[1]+b[3])/2);ctx.strokeStyle='#9db29a';ctx.lineWidth=2/scale;ctx.stroke(this.path);for(const [st,color]of [[snapshot.opponent,'#b8dce4'],[s,'#efc9a8']])if(st){ctx.fillStyle=color;ctx.beginPath();ctx.arc(st.x,st.y,3/scale,0,7);ctx.fill();}ctx.restore();}
 }
}
