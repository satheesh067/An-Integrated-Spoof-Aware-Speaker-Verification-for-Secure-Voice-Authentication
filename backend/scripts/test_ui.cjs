// Contract and rendering smoke checks without installing frontend dependencies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const nodes = new Map();
function node(selector) {
  if (!nodes.has(selector)) nodes.set(selector, {innerHTML:'',textContent:'',style:{},clientWidth:640,clientHeight:90,classList:{toggle(){}},getContext(){return {clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},createImageData(w,h){return {data:new Uint8ClampedArray(w*h*4)}},putImageData(){}}}});
  return nodes.get(selector);
}
const sandbox = {console,Blob,URL,FormData,AbortSignal,Date,Math,Float32Array,Float64Array,Uint8ClampedArray,DataView,ArrayBuffer,Number,String,JSON,Error,setTimeout,clearTimeout,setInterval,clearInterval,confirm:()=>false,fetch:async()=>{throw Error('Test backend offline')},localStorage:{getItem(){return null},setItem(){}},location:{hash:''},navigator:{},document:{querySelector:node,addEventListener(){},createElement(){return {click(){}}}},window:{devicePixelRatio:1,addEventListener(){},scrollTo(){}}};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('frontend/app.js','utf8'),sandbox);
(async()=>{
  await new Promise(resolve=>setTimeout(resolve,5));
  for(const page of ['dashboard','authenticate','analysis','results','users','history','benchmark','settings']){
    vm.runInContext(`S.page='${page}';render()`,sandbox);
    assert(node('#main').innerHTML.includes('<h1>'),`${page} renders`);
    assert(!node('#main').innerHTML.includes('undefined'),`${page} contains no undefined values`);
  }
  vm.runInContext(`S.challenge={challenge_phrase:'clear star 95',expires_at:Date.now()/1000+20};S.page='authenticate';render()`,sandbox);
  assert(node('#main').innerHTML.includes('clear star 95'),'API challenge_phrase is displayed');
  vm.runInContext(`S.result={decision:'ACCESS_DENIED',verdict_type:'SUSPECTED_SPOOF',claimed_user:'<script>',fused_score:1.674,speaker_score:.5626,spoof_score:-11.3603,fusion_threshold:.0783,speaker_threshold:.313,spoof_threshold:-4.0694,reasons:['Gate failed'],enforced_policy:'strict_security'};S.page='results';render()`,sandbox);
  assert(node('#main').innerHTML.includes('strict_security'));
  assert(node('#main').innerHTML.includes('-11.3603'));
  assert(node('#main').innerHTML.includes('&lt;script&gt;'),'server strings are escaped');
  assert(!node('#main').innerHTML.includes('<script>'));
  const blob=vm.runInContext('wav(new Float32Array(48000).fill(.5),48000)',sandbox);
  const header=new DataView(await blob.arrayBuffer());
  assert.equal(header.getUint32(24,true),16000);
  assert.equal(header.getUint16(22,true),1);
  assert.equal(header.getUint32(40,true),32000);
  assert.equal(blob.size,32044);
  vm.runInContext(`S.buffer={sampleRate:16000,numberOfChannels:1,length:16000,duration:1,getChannelData(){return new Float32Array(16000)}};S.page='analysis';render()`,sandbox);
  assert(node('#main').innerHTML.includes('Time-frequency spectrogram'));
  vm.runInContext(`S.blob=new Blob(['test']);S.challenge={expires_at:0};verify().then(()=>{throw Error('Expired challenge was accepted')},e=>{if(!e.message.includes('expired'))throw e})`,sandbox);
  vm.runInContext(`S.busy=false;S.challengeUser='speaker_alpha';S.challenge={session_id:'fresh-token',expires_at:Date.now()/1000+45};S.blob=new Blob(['audio']);`,sandbox);
  node('#speaker').value='speaker_alpha';
  let sent;
  sandbox.fetch=async(url,options)=>{if(url==='/api/v1/authenticate')sent={url,options};return {ok:true,json:async()=>({decision:'ACCESS_DENIED',verdict_type:'CHALLENGE_FAILED',claimed_user:'speaker_alpha',reasons:['Wrong phrase']})}};
  await vm.runInContext('verify()',sandbox);
  assert.equal(sent.url,'/api/v1/authenticate');
  assert.equal(sent.options.body.get('session_id'),'fresh-token');
  assert.equal(sent.options.body.get('username'),'speaker_alpha');
  assert.equal(vm.runInContext('S.busy',sandbox),false);
  assert.equal(vm.runInContext('S.challenge',sandbox),null);
  assert.equal(vm.runInContext('S.page',sandbox),'results');
  assert(node('#main').innerHTML.includes('Wrong phrase'));
  const diagnostics=vm.runInContext(`signalRegions({sampleRate:100,duration:.3,getChannelData:()=>new Float32Array([1,...Array(9).fill(.1),...Array(10).fill(0),...Array(10).fill(.2)])})`,sandbox);
  assert.equal(diagnostics[0].kind,'clipping');assert.equal(diagnostics[1].kind,'low energy');
  assert.equal(diagnostics[1].start,.1);assert.equal(diagnostics[1].end,.2);
  vm.runInContext(`S.challenge={session_id:'retry-token',expires_at:Date.now()/1000+45};S.page='authenticate'`,sandbox);
  sandbox.fetch=async()=>{throw Error('Connection lost')};
  await assert.rejects(vm.runInContext('verify()',sandbox),/Connection lost/);
  assert.equal(vm.runInContext('S.busy',sandbox),false);
  vm.runInContext(`S.page='authenticate';render()`,sandbox);
  assert(node('#main').innerHTML.includes('signal-pair'),'reference and live plots share a paired layout');
  assert(node('#main').innerHTML.includes('Reference voice'));
  assert(node('#main').innerHTML.includes('Live recording'));
  assert(!node('#main').innerHTML.includes('Before you begin'),'authentication clutter removed');
  assert(node('#main').innerHTML.includes('Test With AI'),'synthetic demo section renders');
  vm.runInContext(`S.result={decision:'ACCESS_DENIED',verdict_type:'SPEAKER_MISMATCH',claimed_user:'alice',speaker_score:.1,speaker_threshold:.3,spoof_score:1,spoof_threshold:-4,fused_score:-2,fusion_threshold:.5,reasons:[],evidence:{speaker:{reference_embedding:[1,0],probe_embedding:[0,1]},fusion:{speaker_contribution:1,countermeasure_contribution:.2,bias:-3.2,require_cm_gate:true}}};S.page='results';render()`,sandbox);
  assert(node('#main').innerHTML.includes('data-evidence="speaker"'));
  assert(node('#main').innerHTML.includes('data-evidence="countermeasure"'));
  assert(node('#main').innerHTML.includes('data-evidence="fusion"'));
  assert(node('#main').innerHTML.includes('mandatory anti-spoof gate'));
  assert(!node('#main').innerHTML.includes('NaN'));
  console.log('PASS: eight page renders, challenge contract, result escaping, WAV format/resampling, spectrogram render, and expiry rejection.');
})().catch(err=>{console.error(err);process.exitCode=1});
