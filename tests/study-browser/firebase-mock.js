/* 시험 전용 Firebase compat 대역 — 운영 Firestore/Storage 에 절대 접속하지 않는다.
   데이터는 시험 서버 주소(localhost)의 localStorage 에만 저장되고, 같은 주소의 다른 탭과 storage 이벤트로 동기화된다(동시 편집 시험용).
   window.__mockFail = 'offline' 이면 모든 쓰기/트랜잭션이 실패한다. */
(function(){
  var KEY='__mockfs_v1';
  var listeners=[];
  function load(){ try{ return JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(e){ return {}; } }
  function save(db){ localStorage.setItem(KEY, JSON.stringify(db)); }
  function col(db,name){ return db[name]||(db[name]={}); }
  function autoId(){ return 'm'+Date.now().toString(36)+Math.random().toString(36).slice(2,10); }
  function clone(v){ return v==null?v:JSON.parse(JSON.stringify(v)); }
  function fail(){ if(window.__mockFail==='offline') return Promise.reject(new Error('Failed to get document because the client is offline.')); return null; }
  window.__mockStats={writes:0,reads:0,txns:0,lastBytes:0};
  function notify(){ listeners.slice().forEach(function(l){ try{ l(); }catch(e){ console.error(e); } }); }
  window.addEventListener('storage', function(e){ if(e.key===KEY) notify(); });
  function docSnap(name,id){ var d=col(load(),name)[id]; return {id:id, exists:!!d, data:function(){ return clone(d); }, metadata:{fromCache:false,hasPendingWrites:false}, ref:new DocRef(name,id)}; }
  function DocRef(name,id){ this._c=name; this.id=id||autoId(); }
  DocRef.prototype.get=function(){ var f=fail(); if(f) return f; window.__mockStats.reads++; return Promise.resolve(docSnap(this._c,this.id)); };
  DocRef.prototype.set=function(data,opt){ var f=fail(); if(f) return f; var db=load(), c=col(db,this._c); c[this.id]=(opt&&opt.merge)?Object.assign({},c[this.id]||{},clone(data)):clone(data); window.__mockStats.writes++; window.__mockStats.lastBytes=JSON.stringify(c[this.id]).length; save(db); notify(); return Promise.resolve(); };
  DocRef.prototype.update=function(data){ var f=fail(); if(f) return f; var db=load(), c=col(db,this._c); if(!c[this.id]) return Promise.reject(new Error('No document to update')); Object.assign(c[this.id], clone(data)); window.__mockStats.writes++; window.__mockStats.lastBytes=JSON.stringify(c[this.id]).length; save(db); notify(); return Promise.resolve(); };
  DocRef.prototype.delete=function(){ var f=fail(); if(f) return f; var db=load(); delete col(db,this._c)[this.id]; window.__mockStats.writes++; save(db); notify(); return Promise.resolve(); };
  DocRef.prototype.onSnapshot=function(next){ var self=this; var fire=function(){ next(docSnap(self._c,self.id)); }; listeners.push(fire); setTimeout(fire,0); return function(){ listeners=listeners.filter(function(x){ return x!==fire; }); }; };
  function Query(name,filters,order){ this._c=name; this._f=filters||[]; this._o=order||null; }
  Query.prototype.where=function(field,op,val){ return new Query(this._c,this._f.concat([[field,op,val]]),this._o); };
  Query.prototype.orderBy=function(field,dir){ return new Query(this._c,this._f,[field,dir||'asc']); };
  Query.prototype.doc=function(id){ return new DocRef(this._c,id); };
  Query.prototype.add=function(data){ var ref=new DocRef(this._c); return ref.set(data).then(function(){ return ref; }); };
  Query.prototype._rows=function(){ var c=col(load(),this._c), f=this._f, o=this._o; var rows=Object.keys(c).map(function(id){ return {id:id,d:c[id]}; }).filter(function(r){ return f.every(function(x){ var v=r.d[x[0]]; if(x[1]==='>=') return v>=x[2]; if(x[1]==='=='||x[1]==='==') return v===x[2]; if(x[1]==='array-contains') return (v||[]).indexOf(x[2])>=0; return true; }); }); if(o) rows.sort(function(a,b){ var x=a.d[o[0]], y=b.d[o[0]]; var r=x<y?-1:x>y?1:0; return o[1]==='desc'?-r:r; }); return rows; };
  Query.prototype.get=function(){ var self=this; return Promise.resolve({docs:self._rows().map(function(r){ return {id:r.id,data:function(){ return clone(r.d); }}; })}); };
  Query.prototype.onSnapshot=function(next){ var self=this; var fire=function(){ window.__mockStats.reads++; next({docs:self._rows().map(function(r){ return {id:r.id,data:function(){ return clone(r.d); }}; }), metadata:{fromCache:false,hasPendingWrites:false}}); }; listeners.push(fire); setTimeout(fire,0); return function(){ listeners=listeners.filter(function(x){ return x!==fire; }); }; };
  var firestore={ collection:function(n){ return new Query(n); },
    runTransaction:function(fn){ var f=fail(); if(f) return f; window.__mockStats.txns++; var writes=[]; var tx={ get:function(ref){ return Promise.resolve(docSnap(ref._c,ref.id)); }, set:function(ref,data,opt){ writes.push(function(){ return ref.set(data,opt); }); return tx; }, update:function(ref,data){ writes.push(function(){ return ref.update(data); }); return tx; } };
      return Promise.resolve(fn(tx)).then(function(res){ var delay=window.__mockTxnDelay||0; return new Promise(function(ok){ setTimeout(ok,delay); }).then(function(){ var f2=fail(); if(f2) return f2; return writes.reduce(function(p,w){ return p.then(w); }, Promise.resolve()).then(function(){ return res; }); }); }); } };
  var uploads=[];
  window.__mockUploads=uploads;
  var storage={ ref:function(path){ return { put:function(blob,meta){ var f=fail(); if(f) return f; return fetch('/__test/upload?path='+encodeURIComponent(path),{method:'POST',headers:{'content-type':(meta&&meta.contentType)||blob.type||'application/octet-stream'},body:blob}).then(function(r){ if(!r.ok) throw new Error('upload '+r.status); return r.json(); }).then(function(j){ uploads.push({path:path,size:blob.size,url:j.url}); return {ref:{getDownloadURL:function(){ return Promise.resolve(j.url); }}}; }); }, delete:function(){ uploads.push({deleted:path}); return Promise.resolve(); } }; } };
  var user={uid:'test-user'};
  var auth={ currentUser:user, signInAnonymously:function(){ return Promise.resolve({user:user}); }, onAuthStateChanged:function(cb){ setTimeout(function(){ cb(user); },0); return function(){}; } };
  var app={ firestore:function(){ return firestore; }, auth:function(){ return auth; }, storage:function(){ return storage; } };
  window.firebase={ apps:[], initializeApp:function(){ this.apps.push(app); return app; }, app:function(){ return app; }, firestore:function(){ return firestore; }, storage:function(){ return storage; }, auth:function(){ return auth; } };
  window.__mockReset=function(data){ save(data||{}); notify(); };
  window.__mockDump=function(){ return load(); };
  console.log('[시험] Firebase 대역 사용 중 — 운영 데이터 접속 없음');
})();
