// Static preview only. No model results or API responses are simulated.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../frontend');
const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'};
http.createServer((req,res)=>{
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname === '/' || pathname === '/app') { res.writeHead(302,{Location:'/ui/'}); return res.end(); }
  if (!pathname.startsWith('/ui/')) { res.writeHead(503,{'Content-Type':'application/json'}); return res.end(JSON.stringify({detail:'Static preview: configure a running backend in Settings.'})); }
  const file = path.resolve(root, pathname.slice(4) || 'index.html');
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  fs.readFile(file,(err,data)=>{if(err){res.writeHead(404);return res.end();}res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});res.end(data);});
}).listen(3000,'127.0.0.1',()=>console.log('VoiceGuard preview: http://127.0.0.1:3000/ui/'));
