// Explicit live Firebase development server. Loopback only; no mock SDK and no credentials.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),port=Number(process.argv[2]||8925);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};
http.createServer((req,res)=>{
  let name;try{name=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\//,'');}catch(_){res.writeHead(400).end();return;}
  const file=path.resolve(root,name);
  if(!file.startsWith(root+path.sep)||!(name==='records.html'||name==='tools/records-snapshot.html'||name.startsWith('js/'))){res.writeHead(404).end();return;}
  fs.readFile(file,(e,b)=>{res.writeHead(e?404:200,{'content-type':types[path.extname(file)]||'text/plain','cache-control':'no-store'});res.end(e?'Not found':b);});
}).listen(port,'127.0.0.1',()=>console.log('LIVE Firebase development preview: http://localhost:'+port+'/records.html'));
