'use strict';
const paths={dashboard:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8',wave:'M2 12h3l3-8 4 16 4-12 3 4h3',shield:'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6',users:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3 M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 8 M22 21v-3a4 4 0 0 0-3-4',clock:'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20 M12 6v6l4 2',chart:'M4 3v18h17 M8 16v-5 M13 16V7 M18 16V4',settings:'M4 4v16 M12 4v16 M20 4v16 M1 8h6 M9 16h6 M17 10h6',arrow:'M5 12h14 M14 7l5 5-5 5',upload:'M12 16V3 M7 8l5-5 5 5 M3 15v6h18v-6',stop:'M6 6h12v12H6z',play:'M7 4l14 8-14 8z',check:'M5 12l4 4L20 5',file:'M14 2H5v20h14V7z M14 2v6h5 M8 12h8 M8 16h8'};
const icon=n=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[n]||paths.shield}"/></svg>`;
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pages=[['dashboard','Overview','dashboard'],['authenticate','Live authentication','mic'],['analysis','Audio analysis','wave'],['results','Verification results','shield'],['users','User management','users'],['history','Detection history','clock'],['benchmark','Research & benchmarks','chart'],['settings','Settings','settings']];
const S={page:'dashboard',online:false,health:null,users:[],history:[],recordings:[],recordingId:null,result:null,challenge:null,challengeUser:null,blob:null,buffer:null,url:null,name:'',recording:false,busy:false,api:localStorage.getItem('voiceguard-api')||'',logs:[],enrollFiles:[],userError:'',syntheticSource:false,demoVoice:'default',error:'',reference:null,referenceUser:null,referenceMessage:'Select a speaker to load their enrolled reference.',enrollPhrases:['The quick brown fox jumps over the lazy dog near the riverbank.','My voice is my unique biometric passport for secure system access.','VoiceGuard AI verifies genuine identity using neural speech authentication.'],enrollIndex:0,enrollRecordings:[null,null,null],enrollRecording:false,enrollUsername:''};
let context,processor,source,stream,chunks=[],recordTimer,challengeTimer,recordStarted=0,toastTimer,enrollProcessor,enrollSource,enrollChunks=[],enrollTimer,enrollStarted=0;
function toast(message){S.error=message;const alert=$('#workflow-error');if(alert){alert.textContent=message;alert.hidden=false}$('#toast').textContent=message;$('#toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').style.display='none',6000)}
function log(message){S.logs.unshift({time:new Date().toLocaleTimeString(),message});S.logs=S.logs.slice(0,30)}
async function api(path,options={}){const res=await fetch(`${S.api}${path}`,{...options,signal:AbortSignal.timeout(180000)});const text=await res.text();let data;try{data=JSON.parse(text)}catch{throw Error(`Server response error (${res.status}): ${text.slice(0,250)}`)}if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));return data}
async function refresh(){try{S.health=await api('/health');S.online=true;log('Backend health check succeeded.')}catch(e){S.online=false;log(`Connection: ${e.message}`)}$('#connection').textContent=S.online?'Backend connected':'Backend offline';$('#status-dot').classList.toggle('online',S.online);$('#device').textContent=S.online?(S.health.gpu_name||S.health.device.toUpperCase())+' · API available':'Start the local API on port 8000';render();if(S.online){try{S.users=(await api('/api/v1/users')).enrolled_users;await reloadRecordingHistory();S.userError=''}catch(e){S.userError=e.message;log(`Enrollment list: ${e.message}`)}render()}}
function heading(title,description,action=''){return `<div class="page-heading"><div><h1>${title}</h1><p>${description}</p></div>${action}</div>`}
function button(label,action,type='',i=''){return `<button class="button ${type}" data-action="${action}" ${S.busy?'disabled':''}>${i?icon(i):''}${label}</button>`}
function card(title,body,span=12,extra=''){return `<section class="card col${span}"><div class="card-title"><h2>${title}</h2>${extra}</div>${body}</section>`}
function empty(text,i='clock'){return `<div class="empty">${icon(i)}${text}</div>`}
function stat(label,value,note,i,color=''){return `<section class="card col4"><div class="stat"><span class="stat-label">${label}</span><span class="stat-icon ${color}">${icon(i)}</span></div><div class="stat-value">${value}</div><span class="pill ${color==='green'?'green':'gray'}">${label==='Enrolled speakers'?'Voiceprint registry':'This browser session'}</span><div class="stat-note">${note}</div></section>`}
function layer(title,description,i,color=''){return `<div class="layer"><span class="stat-icon ${color}">${icon(i)}</span><div><h3>${title}</h3><p>${description}</p></div><span class="pill gray">Integrated</span></div>`}
function steps(){return `<div class="steps">${['Select identity','Speak challenge','Run checks','View decision'].map((s,i)=>`<div class="step ${i===0||S.challenge?'active':''}"><b>${i+1}</b>${s}</div>`).join('')}</div>`}
function recorder(){return `<div class="recorder ${S.recording?'recording':''}"><div class="mic-orb">${icon('mic')}</div><h3>${S.recording?'Listening to your voice…':S.blob?'Recording ready':'Your voice. Your identity.'}</h3><canvas class="wave" id="waveform" aria-label="Audio waveform"></canvas><p id="record-time">${S.recording?'Speak naturally, then stop and verify.':S.blob?esc(S.name):'Record a fresh challenge response in a quiet environment.'}</p><div class="recorder-controls">${button(S.recording?'Stop recording':'Start recording',S.recording?'stop':'record',S.recording?'danger':'primary',S.recording?'stop':'mic')}${S.blob&&!S.recording?button('Clear','clear','',''):''}</div>${S.url?`<audio controls src="${S.url}"></audio>`:''}</div>`}
function userSelect(){return `<div class="form-field"><label for="speaker">Speaker identity</label><select id="speaker" ${S.busy||S.recording?'disabled':''}><option value="">Select an enrolled speaker</option>${S.users.map(u=>`<option value="${esc(u.username)}" ${S.challengeUser===u.username?'selected':''}>${esc(u.username)}</option>`).join('')}</select></div>`}
function sessionsTable(entries=S.history){return entries.length?`<div class="table-wrap"><table><thead><tr><th>SPEAKER</th><th>DECISION</th><th>RESULT</th><th>TIME</th><th></th></tr></thead><tbody>${entries.map(r=>`<tr><td><b>${esc(r.claimed_user)}</b></td><td><span class="pill ${r.decision==='ACCESS_GRANTED'?'green':'red'}">${r.decision==='ACCESS_GRANTED'?'Access granted':'Access denied'}</span></td><td>${esc((r.verdict_type==='SUSPECTED_SPOOF'?'ANTI-SPOOF CHECK DID NOT PASS':r.verdict_type.replaceAll('_',' ')).toLowerCase())}</td><td>${esc(r.localTime)}</td><td><button class="button" data-result="${S.history.indexOf(r)}">View</button></td></tr>`).join('')}</tbody></table></div>`:empty('No verifications yet. Your session activity will appear here.')}
function overview(){return heading('Security starts with a voice.','Your voice authentication workspace, at a glance.',`<a class="button" href="#users">${icon('users')}Manage speakers</a>`)+`<section class="hero"><div><div class="eyebrow">INTELLIGENT VOICE PROTECTION</div><h2>A familiar voice isn’t always a real one.</h2><p>Verify who’s speaking. Detect synthetic speech. Check a fresh spoken challenge — all in one workflow.</p><a href="#authenticate" class="button primary">${icon('mic')}Start verification ${icon('arrow')}</a></div><div class="hero-art">${Array.from({length:65},(_,i)=>`<i style="height:${12+Math.abs(Math.sin(i*1.71)*Math.cos(i*.13))*100}px"></i>`).join('')}<div class="shield-art">${icon('shield')}</div></div></section><div class="grid">${stat('Enrolled speakers',S.online?S.users.length:'—','Verified enrollment · 192-dimensional voiceprints','users')}${stat('Voice verifications',S.history.length,'Fresh challenges · Single-use sessions','mic')}${stat('Access denied',S.history.filter(r=>r.decision!=='ACCESS_GRANTED').length,'Review the reasons for every decision','shield','green')}${card('Live authentication',steps()+`<div class="recorder"><div class="mic-orb">${icon('mic')}</div><h3>Ready when you are.</h3><canvas class="wave" id="waveform"></canvas><p>Select your identity and speak a randomly generated phrase.</p><a href="#authenticate" class="button primary">${icon('mic')}Begin authentication</a></div>`,8,`<span class="pill gray">Challenge required</span>`)}${card('Three layers. One decision.',layer('Speaker identity','ECAPA-TDNN · Voiceprint matching','users')+layer('Audio authenticity','AASIST · Anti-spoof countermeasure','shield','green')+layer('Fresh spoken challenge','Whisper · Phrase and number verification','wave','purple')+`<div class="info">Decisions use the server’s calibrated policy. Results remain experimental and require validation beyond the pilot dataset.</div>`,4)}${card('Recent verifications',sessionsTable(S.history.slice(0,4)),12,`<a href="#history" class="link">View session history →</a>`)}</div>`}
function authentication(){return heading('Voice verification','Select your identity, speak the phrase, and compare the signals.',`<span class="session-badge"><i></i>${S.recording?'Recording live':S.busy?'Analyzing audio':'Ready to listen'}</span>`)+`<div class="verify-layout"><section class="card capture-card"><div class="card-title"><h2>1. Record your response</h2><span class="pill gray">Secure challenge</span></div>${userSelect()}${button('New challenge','challenge','','shield')}${S.challenge?`<div class="challenge"><span class="subtle">SAY THIS PHRASE</span><strong>${esc(S.challenge.challenge_phrase)}</strong><span class="pill" id="ttl"></span></div>`:'<div class="challenge placeholder"><p>Choose a speaker and request a new phrase.</p></div>'}<div id="workflow-error" role="alert" class="info danger-note" ${S.error?'':'hidden'}>${esc(S.error)}</div><div class="capture-status"><span class="mic-orb">${icon('mic')}</span><div><h3>${S.recording?'Listening…':S.blob?'Audio captured':'Microphone ready'}</h3><p id="record-time">${S.recording?'Speak naturally, then stop.':S.blob?esc(S.name):'Use a quiet room and your natural voice.'}</p></div></div><div class="recorder-controls">${button(S.recording?'Stop recording':'Record voice',S.recording?'stop':'record',S.recording?'danger':'primary',S.recording?'stop':'mic')}${S.blob&&!S.recording?button('Clear','clear'):''}</div>${S.url?`<audio controls src="${S.url}"></audio>`:''}<div class="verify-action">${button(S.busy?'Analyzing…':'Verify identity','verify','primary','arrow')}</div><details class="upload-details"><summary>Use an audio file instead</summary><input type="file" id="probe-file" accept="audio/*" aria-label="Upload a challenge response"></details></section><section class="card comparison-card"><div class="card-title"><div><span class="eyebrow">SIGNAL COMPARISON</span><h2>One identity. Two voice signals.</h2></div><span class="pill gray">${S.buffer?'Audio ready':'Awaiting recording'}</span></div>${comparison()}</section></div>${aiDemoSection()}${S.result?`<section class="card latest-card"><div class="card-title"><h2>Verification summary</h2></div>${resultView()}</section>`:''}`}
function resultView(){const r=S.result;if(!r)return empty('Complete a live verification to see model scores and the final decision.','shield');const granted=r.decision==='ACCESS_GRANTED';return `<div class="result ${granted?'granted':'denied'}"><span class="pill ${granted?'green':'red'}">${esc((r.verdict_type==='SUSPECTED_SPOOF'?'ANTI-SPOOF CHECK DID NOT PASS':r.verdict_type.replaceAll('_',' ')))}</span><h2 style="font-size:24px;margin:14px 0 8px">${granted?'Identity verified. Access granted.':'Verification did not pass.'}</h2><p>Speaker: <b>${esc(r.claimed_user)}</b> · Enforced policy: <b>${esc(r.enforced_policy||'Not reported')}</b></p>${(r.reasons||[]).map(reason=>`<p>${esc(reason)}</p>`).join('')}${r.verdict_type==='SUSPECTED_SPOOF'&&r.source_type!=='synthetic_demo'?'<div class="info">This detector can reject genuine speech. A low score does not prove the speaker is fake. Retry with a direct microphone, a quiet room, and a natural complete phrase. If the check keeps failing, this microphone and speaker need validated calibration.</div>':''}</div><div class="score-grid">${[['Speaker similarity',r.speaker_score,r.speaker_threshold],['Anti-spoof score',r.spoof_score,r.spoof_threshold],['Fused decision score',r.fused_score,r.fusion_threshold]].map(([title,value,threshold])=>`<div class="score ${Number.isFinite(value)&&value!==-999&&Number.isFinite(threshold)?value>=threshold?'passed-score':'failed-score':''}"><span class="subtle">${title}</span><strong>${Number.isFinite(value)&&value!==-999?value.toFixed(4):'Unavailable'}</strong><small>Threshold: ${Number.isFinite(threshold)?threshold.toFixed(4):'Not reported'}</small><div class="gate-status">${Number.isFinite(value)&&value!==-999&&Number.isFinite(threshold)?value>=threshold?'Threshold met':'Below threshold':r.verdict_type==='CHALLENGE_FAILED'?'Not run: spoken challenge failed':'Check not completed'}</div></div>`).join('')}</div>${evidencePanels(r)}${challengeSummary(r)}<div class="info">Raw scores are model outputs, not probabilities. Calibration: ${esc(r.calibration_status||'Not reported')} · ${esc(r.calibration_source||'Not reported')}</div><details style="margin-top:18px"><summary>Challenge checks & processing telemetry</summary><pre>${esc(JSON.stringify({challenge:r.challenge_status,telemetry:r.telemetry},null,2))}</pre></details><div style="margin-top:18px">${button('Export result JSON','export','','file')}</div>`}
function analysis(){return heading('Listen closer. See the signal.','Inspect the recorded waveform and local audio properties.')+`<div class="grid">${card('Audio workspace',`<label class="upload">${icon('upload')} Choose an audio file to inspect<input id="analysis-file" type="file" accept="audio/*"></label>${S.buffer?`<div class="file-name">${esc(S.name)}</div><div class="analysis-meta"><span>Duration <b>${S.buffer.duration.toFixed(2)} s</b></span><span>Decoded rate <b>${S.buffer.sampleRate.toLocaleString()} Hz</b></span><span>Channels <b>${S.buffer.numberOfChannels}</b></span></div><canvas class="wave" id="waveform" style="height:220px"></canvas><audio controls src="${S.url}"></audio><h3 style="margin-top:24px">Time-frequency spectrogram</h3><p class="subtle">Measured short-time Fourier transform · 0 to ${Math.round(S.buffer.sampleRate/2).toLocaleString()} Hz · time from left to right</p><canvas id="spectrogram" style="width:100%;height:210px;margin-top:14px;border-radius:8px" aria-label="Measured audio spectrogram"></canvas>`:empty('Record or upload a sample to view its waveform.','wave')}<div class="info">This waveform shows decoded audio amplitude. Red regions mark clipping; amber regions mark low-energy 100 ms windows. These are signal quality indicators. Model scores apply to the whole clip.</div>`,12)}${card('Enrolled reference & probe',comparison(),12)}${card('Model results',resultView(),12)}</div>`}
function users(){
  const recCount=(S.enrollRecordings||[]).filter(r=>r&&r.blob).length;
  const currentIdx=S.enrollIndex||0;
  const currentPhrase=S.enrollPhrases[currentIdx];
  const currentRec=S.enrollRecordings[currentIdx];
  const isDoneAll=recCount===3;
  
  const stepTabs=S.enrollPhrases.map((phrase,idx)=>{
    const isRecorded=!!S.enrollRecordings[idx];
    const isActive=currentIdx===idx;
    return `<button type="button" class="enroll-step-tab ${isActive?'active':''} ${isRecorded?'completed':''}" data-enroll-index="${idx}" ${S.enrollRecording?'disabled':''}>
      <span class="step-num">${isRecorded?'✓':idx+1}</span>
      <span>Phrase ${idx+1}</span>
      ${isRecorded?`<span style="font-size:10px;opacity:0.85">${S.enrollRecordings[idx].duration.toFixed(1)}s</span>`:''}
    </button>`;
  }).join('');

  const enrollCardHtml=`
    <div class="enroll-container">
      <div class="enroll-id-box">
        <label for="enroll-name">
          ${icon('users')}
          <span>Step 1: Speaker Name or ID</span>
        </label>
        <input id="enroll-name" name="username" required pattern="[a-zA-Z0-9_-]+" maxlength="64" placeholder="Enter speaker name (e.g. alex_smith)" value="${esc(S.enrollUsername)}" ${S.enrollRecording||S.busy?'disabled':''}>
        <span class="subtle" style="display:block;margin-top:6px;font-size:11px">Letters, numbers, underscores and hyphens.</span>
      </div>

      <div class="enroll-voice-box">
        <div class="enroll-voice-header">
          <h3>Step 2: Voice Registration</h3>
          <span class="pill ${isDoneAll?'green':'gray'}">${recCount} of 3 Recorded</span>
        </div>

        <div class="enroll-stepper">
          ${stepTabs}
        </div>

        <div class="enroll-studio ${S.enrollRecording?'is-recording':currentRec?'is-done':''}">
          <div class="studio-header-tag">
            <span class="studio-badge">PHRASE ${currentIdx+1} OF 3</span>
            <span class="studio-status ${S.enrollRecording?'live':currentRec?'done':'idle'}">
              ${S.enrollRecording?'Live Recording...':currentRec?'✓ Recorded & Ready':'Awaiting Speech'}
            </span>
          </div>

          <div class="studio-phrase-card">
            <blockquote class="studio-phrase-text">"${esc(currentPhrase)}"</blockquote>
            <p class="studio-phrase-guide">${S.enrollRecording?'Speak the phrase clearly into your microphone now...':currentRec?'Sample recorded. Listen below or re-record if there was background noise.':'Press "Start Recording" and read the phrase aloud in your natural voice.'}</p>
          </div>

          <div class="studio-wave-box">
            <canvas id="enroll-waveform" class="studio-wave-canvas"></canvas>
            ${S.enrollRecording?`<span class="studio-timer-pill" id="enroll-record-time">0.0s</span>`:''}
          </div>

          <div class="studio-controls-row">
            ${!S.enrollRecording?`
              <button type="button" class="button ${currentRec?'secondary':'primary'} record-action-btn" data-action="enrollRecord">
                ${icon('mic')}${currentRec?'Re-record Phrase':'Start Recording'}
              </button>
            `:`
              <button type="button" class="button danger record-action-btn" data-action="enrollStop">
                ${icon('stop')}Stop Recording
              </button>
            `}

            ${currentRec&&!S.enrollRecording?`
              <audio controls src="${currentRec.url}" style="height:38px"></audio>
              ${currentIdx<2?`
                <button type="button" class="button primary next-action-btn" data-action="enrollNext">
                  Next Phrase (${currentIdx+2}/3) →
                </button>
              `:''}
            `:''}
          </div>
        </div>

        <div class="enroll-progress-bar-wrap">
          <div class="enroll-progress-text">
            <span>Registration Progress: <b>${recCount} / 3</b></span>
            <span>${isDoneAll?'✓ Ready to save':'Record all 3 for maximum precision'}</span>
          </div>
          <div class="enroll-meter">
            <div class="enroll-meter-fill" style="width:${(recCount/3)*100}%"></div>
          </div>
        </div>

        <div style="margin-top:8px">
          <button type="button" class="button primary submit-voiceprint-btn" data-action="enrollSubmit" ${S.busy||recCount===0?'disabled':''}>
            ${icon('users')}${S.busy?'Extracting embeddings & training…':isDoneAll?'✨ Train & Create Voiceprint (3/3 Ready)':recCount>0?`Train with ${recCount} recording(s)`:'Record phrases to train'}
          </button>
          ${isDoneAll?`<p class="enroll-finish-note">✓ All 3 speech samples captured. Click above to complete registration.</p>`:''}
        </div>

        <details class="upload-details" style="margin-top:8px">
          <summary>Or upload audio files manually</summary>
          <label class="upload" style="margin-top:8px">
            ${icon('upload')} Choose WAV files
            <input id="enroll-files" type="file" accept="audio/*" multiple>
          </label>
        </details>
      </div>
    </div>
  `;

  return heading('A voiceprint for every identity.','Enroll genuine speech samples and manage the speaker registry.')+
    `<div class="grid">
      ${card('Register a new speaker',enrollCardHtml,6)}
      ${card('Speaker registry',S.userError?`<div class="info danger-note">${esc(S.userError)}</div>`:S.users.length?`<div class="table-wrap"><table><thead><tr><th>IDENTITY</th><th>RECORDINGS</th><th>CREATED</th><th></th></tr></thead><tbody>${S.users.map(u=>`<tr><td><b>${esc(u.username)}</b><br><span class="subtle">${esc(u.embedding_dim)} dimensions</span></td><td>${esc(u.num_recordings)}</td><td>${esc(u.created_at?.slice(0,10)||'—')}</td><td><button class="button danger" data-delete="${esc(u.username)}">Delete</button></td></tr>`).join('')}</tbody></table></div>`:empty(S.online?'No speakers enrolled. Create your first voiceprint.':'Connect the backend to load enrolled speakers.','users'),6,`<span class="pill gray">${S.users.length} speakers</span>`)}
    </div>`;
}

function settings(){return heading('Make the workspace yours.','Connection details and a transparent view of the system.')+`<div class="grid">${card('Backend connection',`<form id="settings-form"><div class="form-field"><label for="api-base">API base URL</label><input type="url" id="api-base" placeholder="Same origin (recommended)" value="${esc(S.api)}"><p class="subtle">Leave blank when served by FastAPI. For a separate UI server, use http://127.0.0.1:8000.</p></div><button class="button primary" type="submit">Save & reconnect</button></form><div class="info">Security policy and thresholds are controlled by the server. The frontend cannot override them. Audio samples are archived by the backend; recordings and results are saved in local server history.</div>`,6)}${card('System telemetry',S.health?Object.entries(S.health).map(([k,v])=>`<div class="model-row"><b>${esc(k.replaceAll('_',' '))}</b><span>${esc(v)}</span></div>`).join(''):empty('Backend telemetry is unavailable.','settings'),6)}${card('Connection activity',S.logs.length?`<pre>${S.logs.map(l=>`${esc(l.time)}  ${esc(l.message)}`).join('\n')}</pre>`:empty('No connection events yet.'),12)}</div>`}
function benchmark(){return heading('Evidence behind the decision.','Inspect saved evaluation metrics from the backend.')+`<div class="grid">${card('Benchmark evaluation',`<div id="benchmark-data">${empty('Load the saved benchmark comparison to inspect the results.','chart')}</div>${button('Load benchmark results','benchmark','primary','chart')}<div class="info">The project guide describes a 21-trial pilot evaluation with a genuine-acceptance tradeoff. The benchmark endpoint labels its response as the official evaluation; validate the CSV provenance before making an official benchmark claim.</div>`,12)}</div>`}
function render(){const selected=pages.find(p=>p[0]===S.page)||pages[0];$('#nav').innerHTML=pages.filter(p=>['authenticate','users','results','history','settings'].includes(p[0])).map(([id,label,i])=>`<a href="#${id}" class="${S.page===id?'active':''}" ${S.page===id?'aria-current="page"':''}>${icon(i)}${label}</a>`).join('');$('#breadcrumb').textContent=selected[1];const views={dashboard:overview,authenticate:authentication,analysis,results:()=>heading('Every check, explained.','Model scores, thresholds and reasons from the latest verification.')+`<div class="grid">${card('Voice comparison',comparison())}${card('Verification result',resultView())}</div>`,users,history:()=>heading('Recording history','Saved audio and verification results, available after reload.')+`<div class="grid">${card('All recordings',recordingTable())}</div>`,benchmark,settings};$('#main').innerHTML=(!S.online?`<div class="connection-warning">Backend unavailable. Start the API to enroll speakers and run verification. <a class="link" href="#settings">Connection settings →</a></div>`:'')+views[S.page]();drawComparison();drawWave();drawEvidence();drawSpectrogram();drawEnrollWave();updateTTL()}
function drawSpectrogram(){
  const canvas=$('#spectrogram');if(!canvas||!S.buffer)return;
  const samples=S.buffer.getChannelData(0),n=512,width=Math.max(1,Math.min(700,Math.floor(canvas.clientWidth))),height=256;
  canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d'),image=ctx.createImageData(width,height);
  const real=new Float64Array(n),imag=new Float64Array(n);
  for(let x=0;x<width;x++){
    const start=Math.floor(x/width*Math.max(0,samples.length-n));
    for(let i=0;i<n;i++){real[i]=(samples[start+i]||0)*(.5-.5*Math.cos(2*Math.PI*i/(n-1)));imag[i]=0}
    for(let i=1,j=0;i<n;i++){let bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j){[real[i],real[j]]=[real[j],real[i]]}}
    for(let len=2;len<=n;len<<=1){const angle=-2*Math.PI/len;for(let i=0;i<n;i+=len){for(let j=0;j<len/2;j++){const a=i+j,b=a+len/2,cos=Math.cos(angle*j),sin=Math.sin(angle*j),r=real[b]*cos-imag[b]*sin,im=real[b]*sin+imag[b]*cos;real[b]=real[a]-r;imag[b]=imag[a]-im;real[a]+=r;imag[a]+=im}}}
    for(let y=0;y<height;y++){const bin=height-1-y,db=20*Math.log10(Math.hypot(real[bin],imag[bin])/n+1e-9),v=Math.max(0,Math.min(1,(db+90)/75)),p=(y*width+x)*4;image.data[p]=Math.round(18+v*120+v*v*100);image.data[p+1]=Math.round(29+v*80+v*v*130);image.data[p+2]=Math.round(54+Math.sin(v*Math.PI)*125);image.data[p+3]=255}
  }
  ctx.putImageData(image,0,0);
}
function updateTTL(){const el=$('#ttl');if(!el||!S.challenge)return;const left=Math.max(0,Math.ceil(S.challenge.expires_at-Date.now()/1000));el.textContent=left?`${left}s remaining`:'Expired — generate a new challenge';el.className='pill '+(left?'':'red')}
async function prepareMic(){if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone access requires localhost or HTTPS and a supported browser.');if(!stream){stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}})}if(!context)context=new AudioContext();await context.resume()}
function releaseMic(){stream?.getTracks().forEach(t=>t.stop());stream=null;source?.disconnect();processor?.disconnect();processor=null;source=null;enrollSource?.disconnect();enrollProcessor?.disconnect();enrollSource=null;enrollProcessor=null}
async function record(){if(S.page!=='authenticate')return;if(S.busy)return;if(!S.challenge||S.challenge.expires_at<=Date.now()/1000)throw Error('Generate a fresh challenge first.');await prepareMic();clearAudio();chunks=[];source=context.createMediaStreamSource(stream);processor=context.createScriptProcessor(4096,1,1);processor.onaudioprocess=e=>{if(S.recording)chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))};source.connect(processor);processor.connect(context.destination);S.recording=true;recordStarted=Date.now();render();recordTimer=setInterval(()=>{drawWave();drawComparison();const el=$('#record-time');if(el)el.textContent=`${((Date.now()-recordStarted)/1000).toFixed(1)} seconds · Stop and submit before expiry`;if(Date.now()-recordStarted>=12000||Date.now()/1000>=S.challenge.expires_at-2)stopRecording()},100)}
function wav(samples,rate){const targetRate=16000,outLength=Math.floor(samples.length*targetRate/rate),data=new ArrayBuffer(44+outLength*2),v=new DataView(data);function str(at,s){for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i))}str(0,'RIFF');v.setUint32(4,36+outLength*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,targetRate,true);v.setUint32(28,targetRate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,outLength*2,true);for(let i=0;i<outLength;i++){const begin=Math.floor(i*rate/targetRate),end=Math.min(samples.length,Math.max(begin+1,Math.floor((i+1)*rate/targetRate)));let sum=0;for(let j=begin;j<end;j++)sum+=samples[j];const n=Math.max(-1,Math.min(1,sum/(end-begin)));v.setInt16(44+i*2,n<0?n*32768:n*32767,true)}return new Blob([data],{type:'audio/wav'})}
async function stopRecording(){if(!S.recording)return;S.recording=false;clearInterval(recordTimer);releaseMic();const all=new Float32Array(chunks.reduce((n,c)=>n+c.length,0));let offset=0;chunks.forEach(c=>{all.set(c,offset);offset+=c.length});if(!all.length){toast('No microphone samples were captured. Check microphone permissions and try again.');render();return}S.blob=await encodeCapture(all,context.sampleRate);S.name='challenge-response.wav';S.url=URL.createObjectURL(S.blob);try{S.buffer=await context.decodeAudioData(await S.blob.arrayBuffer())}catch(e){toast('Could not decode recorded audio: '+e.message)}await persistRecording();render()}
function clearAudio(){S.recordingId=null;S.selectedRegion=null;S.syntheticSource=false;if(S.url)URL.revokeObjectURL(S.url);S.blob=null;S.buffer=null;S.url=null;S.name=''}
async function loadAudio(file,persist=true){if(!file)return;if(file.size>40*1024*1024)throw Error('Choose an audio file smaller than 40 MB.');if(!context)context=new AudioContext();const decoded=await context.decodeAudioData(await file.arrayBuffer());const mono=new Float32Array(decoded.length);for(let ch=0;ch<decoded.numberOfChannels;ch++){const d=decoded.getChannelData(ch);for(let i=0;i<mono.length;i++)mono[i]+=d[i]/decoded.numberOfChannels}clearAudio();S.blob=await encodeCapture(mono,decoded.sampleRate);S.buffer=await context.decodeAudioData(await S.blob.arrayBuffer());S.name=file.name;S.url=URL.createObjectURL(S.blob);if(persist)await persistRecording();render()}
async function challenge(needMic=true){const username=$('#speaker')?.value;if(!username)throw Error('Select an enrolled speaker first.');if(S.recording)throw Error('Stop recording before requesting another challenge.');if(needMic)await prepareMic();S.error='';S.busy=true;S.challenge=null;S.challengeUser=username;clearAudio();render();try{S.challenge=await api('/api/v1/challenge?username='+encodeURIComponent(username));clearInterval(challengeTimer);challengeTimer=setInterval(updateTTL,250);log('Issued a fresh challenge for '+username)}catch(e){releaseMic();throw e}finally{S.busy=false;render()}}
async function verify(){if(S.busy)return;if(S.recording)await stopRecording();if(!S.blob)throw Error('Record or upload your challenge response first.');if(!S.challenge||S.challenge.expires_at<=Date.now()/1000)throw Error('The challenge has expired. Generate a new one and record a fresh response.');if($('#speaker')?.value!==S.challengeUser)throw Error('The selected speaker must match the challenge identity.');const form=new FormData();form.append('username',S.challengeUser);form.append('session_id',S.challenge.session_id);if(S.recordingId)form.append('recording_id',S.recordingId);form.append('audio_file',S.blob,'response.wav');form.append('source_type',S.syntheticSource?'synthetic_demo':'microphone_or_upload');S.error='';S.result=null;S.busy=true;S.challenge=null;clearInterval(challengeTimer);releaseMic();render();try{S.result=await api('/api/v1/authenticate',{method:'POST',body:form});Object.defineProperty(S.result,'audioSnapshot',{value:{buffer:S.buffer,reference:S.reference,referenceUser:S.referenceUser,name:S.name,blob:S.blob,syntheticSource:S.syntheticSource}});S.result.localTime=new Date().toLocaleTimeString();S.history.unshift(S.result);await reloadRecordingHistory();log('Authentication: '+S.result.decision);S.page='results';location.hash='results'}finally{S.busy=false;render()}}
async function enroll(form){const name=form.elements.username.value.trim().toLowerCase();const files=$('#enroll-files').files;if(!/^[a-z0-9_-]{1,64}$/.test(name))throw Error('Use a valid speaker ID.');if(!files.length)throw Error('Select at least one audio recording.');if(S.users.some(u=>u.username===name)&&!confirm(`Replace the existing voiceprint for ${name}?`))return;const data=new FormData();data.append('username',name);for(const file of files)data.append('files',file);S.busy=true;render();try{const response=await api('/api/v1/enroll',{method:'POST',body:data});toast(response.message);S.users=(await api('/api/v1/users')).enrolled_users}catch(e){toast(e.message)}finally{S.busy=false;render()}}
async function loadBenchmark(){const data=await api('/api/v1/benchmark');const rows=data.results||[],keys=[...new Set(rows.flatMap(Object.keys))];$('#benchmark-data').innerHTML=`<p class="subtle" style="margin-bottom:18px">${esc(data.evaluation_partition)}</p>`+(rows.length?`<div class="table-wrap"><table><thead><tr>${keys.map(k=>`<th>${esc(k)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${keys.map(k=>`<td>${esc(r[k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:empty('No benchmark rows returned.'))}

async function startEnrollRecording(){
  if(S.busy)return;
  const nameInput=$('#enroll-name');
  const username=(nameInput?.value||S.enrollUsername||'').trim().toLowerCase();
  if(!username){toast('Please enter a speaker name or ID first.');nameInput?.focus();return}
  if(!/^[a-z0-9_-]{1,64}$/.test(username)){toast('Use letters, numbers, underscores, or hyphens for speaker name.');nameInput?.focus();return}
  S.enrollUsername=username;
  await prepareMic();
  enrollChunks=[];
  enrollSource=context.createMediaStreamSource(stream);
  enrollProcessor=context.createScriptProcessor(4096,1,1);
  enrollProcessor.onaudioprocess=e=>{if(S.enrollRecording)enrollChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))};
  enrollSource.connect(enrollProcessor);
  enrollProcessor.connect(context.destination);
  S.enrollRecording=true;
  enrollStarted=Date.now();
  render();
  clearInterval(enrollTimer);
  enrollTimer=setInterval(()=>{
    drawEnrollWave();
    const el=$('#enroll-record-time');
    const elapsed=(Date.now()-enrollStarted)/1000;
    if(el)el.textContent=`${elapsed.toFixed(1)}s`;
    if(elapsed>=12.0)stopEnrollRecording();
  },100);
}

async function stopEnrollRecording(){
  if(!S.enrollRecording)return;
  S.enrollRecording=false;
  clearInterval(enrollTimer);
  enrollSource?.disconnect();
  enrollProcessor?.disconnect();
  enrollSource=null;
  enrollProcessor=null;
  releaseMic();

  const all=new Float32Array(enrollChunks.reduce((n,c)=>n+c.length,0));
  let offset=0;
  enrollChunks.forEach(c=>{all.set(c,offset);offset+=c.length});

  if(all.length<(context?.sampleRate||16000)*0.9){
    toast('Recording was too short (< 1.0s). Please speak the complete phrase.');
    render();
    return;
  }

  let sumSq=0;
  for(let i=0;i<all.length;i++)sumSq+=all[i]*all[i];
  const rms=Math.sqrt(sumSq/all.length);
  if(rms<0.002){
    toast('Audio level is very faint or silent. Please check your microphone volume.');
    render();
    return;
  }

  const blob=await encodeCapture(all,context.sampleRate);
  const buffer=await context.decodeAudioData(await blob.arrayBuffer());
  const url=URL.createObjectURL(blob);
  const idx=S.enrollIndex||0;

  S.enrollRecordings[idx]={blob,buffer,url,duration:buffer.duration,rms,phrase:S.enrollPhrases[idx]};
  toast(`Phrase ${idx+1} captured successfully! Click "Next Phrase" to proceed.`);
  render();
}

function drawEnrollWave(){
  const canvas=$('#enroll-waveform');
  if(!canvas)return;
  const ratio=window.devicePixelRatio||1;
  const w=Math.max(1,canvas.clientWidth);
  const h=canvas.clientHeight||60;
  canvas.width=Math.round(w*ratio);
  canvas.height=Math.round(h*ratio);
  const ctx=canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);

  const idx=S.enrollIndex||0;
  const rec=S.enrollRecordings[idx];

  if(S.enrollRecording&&enrollChunks.length){
    const chunk=enrollChunks[enrollChunks.length-1];
    const bars=32;
    const barWidth=(canvas.width/bars)*0.55;
    const gap=(canvas.width/bars)*0.45;
    const step=Math.max(1,Math.floor(chunk.length/bars));
    const grad=ctx.createLinearGradient(0,0,0,canvas.height);
    grad.addColorStop(0,'#e11d48');
    grad.addColorStop(1,'#6366f1');
    ctx.fillStyle=grad;

    for(let i=0;i<bars;i++){
      let sum=0;
      for(let j=0;j<step;j++){
        const val=chunk[i*step+j]||0;
        sum+=val*val;
      }
      const rms=Math.sqrt(sum/step);
      const barH=Math.max(4*ratio,Math.min(canvas.height-6*ratio,rms*canvas.height*4.5));
      const x=i*(barWidth+gap)+gap/2;
      const y=(canvas.height-barH)/2;
      ctx.beginPath();
      if(ctx.roundRect)ctx.roundRect(x,y,barWidth,barH,3*ratio);
      else ctx.rect(x,y,barWidth,barH);
      ctx.fill();
    }
  }else if(rec&&rec.buffer){
    const data=rec.buffer.getChannelData(0);
    const bars=44;
    const barWidth=(canvas.width/bars)*0.6;
    const gap=(canvas.width/bars)*0.4;
    const step=Math.max(1,Math.floor(data.length/bars));
    ctx.fillStyle='#10b981';

    for(let i=0;i<bars;i++){
      let max=0;
      for(let j=0;j<step;j++){
        const val=Math.abs(data[i*step+j]||0);
        if(val>max)max=val;
      }
      const barH=Math.max(4*ratio,Math.min(canvas.height-8*ratio,max*canvas.height*0.95));
      const x=i*(barWidth+gap)+gap/2;
      const y=(canvas.height-barH)/2;
      ctx.beginPath();
      if(ctx.roundRect)ctx.roundRect(x,y,barWidth,barH,3*ratio);
      else ctx.rect(x,y,barWidth,barH);
      ctx.fill();
    }
  }else{
    ctx.strokeStyle='#e2e8f0';
    ctx.lineWidth=2*ratio;
    ctx.beginPath();
    ctx.moveTo(15*ratio,canvas.height/2);
    ctx.lineTo(canvas.width-15*ratio,canvas.height/2);
    ctx.stroke();

    ctx.fillStyle='#94a3b8';
    ctx.font=`600 ${11*ratio}px sans-serif`;
    ctx.textAlign='center';
    ctx.fillText('Ready · Waveform appears when speaking',canvas.width/2,canvas.height/2+4*ratio);
  }
}

async function submitEnrollment(){
  const nameInput=$('#enroll-name');
  const name=(nameInput?.value||S.enrollUsername||'').trim().toLowerCase();
  if(!/^[a-z0-9_-]{1,64}$/.test(name)){toast('Use a valid speaker ID (letters, numbers, underscores, hyphens).');nameInput?.focus();return}
  const validRecordings=(S.enrollRecordings||[]).filter(r=>r&&r.blob);
  const manualFiles=$('#enroll-files')?.files;

  if(validRecordings.length===0&&(!manualFiles||manualFiles.length===0)){
    toast('Please record the sentences before creating the voiceprint.');
    return;
  }

  if(S.users.some(u=>u.username===name)&&!confirm(`A voiceprint for "${name}" already exists. Replace it with the new live recordings?`))return;

  const data=new FormData();
  data.append('username',name);
  if(validRecordings.length>0){
    validRecordings.forEach((rec,idx)=>{
      data.append('files',rec.blob,`${name}_live_sample_${idx+1}.wav`);
    });
  }else if(manualFiles&&manualFiles.length>0){
    for(const file of manualFiles)data.append('files',file);
  }

  S.busy=true;
  render();
  try{
    const response=await api('/api/v1/enroll',{method:'POST',body:data});
    toast(response.message||`User '${name}' enrolled successfully!`);
    S.enrollRecordings=[null,null,null];
    S.enrollIndex=0;
    S.enrollUsername='';
    S.users=(await api('/api/v1/users')).enrolled_users;
  }catch(e){
    toast(e.message);
  }finally{
    S.busy=false;
    render();
  }
}

function exportResult(){if(!S.result)throw Error('No result to export.');const url=URL.createObjectURL(new Blob([JSON.stringify(S.result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='voiceguard-verification.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
document.addEventListener('click',async e=>{const target=e.target.closest('button');if(!target)return;try{if(target.dataset.recording){await openSavedRecording(target.dataset.recording);return}if(target.dataset.regionStart!==undefined){S.selectedRegion={start:Number(target.dataset.regionStart),end:Number(target.dataset.regionEnd)};drawComparison();drawEvidence();const audio=$('audio');if(audio)audio.currentTime=S.selectedRegion.start;return}if(target.dataset.result!==undefined){S.result=S.history[Number(target.dataset.result)];if(S.result.audioSnapshot){clearAudio();Object.assign(S,S.result.audioSnapshot);if(S.blob)S.url=URL.createObjectURL(S.blob)}location.hash='results';return}if(target.dataset.delete){const user=target.dataset.delete;if(!confirm(`Delete the voiceprint for ${user}? This cannot be undone.`))return;await api('/api/v1/users/'+encodeURIComponent(user),{method:'DELETE'});S.users=(await api('/api/v1/users')).enrolled_users;render();toast('Voiceprint deleted.');return}if(target.dataset.enrollIndex!==undefined){S.enrollIndex=Number(target.dataset.enrollIndex);render();return}
    const actions={challenge,record,ai:generateDemoVoice,stop:stopRecording,verify,clear:()=>{clearAudio();render()},export:exportResult,benchmark:loadBenchmark,enrollRecord:startEnrollRecording,enrollStop:stopEnrollRecording,enrollNext:()=>{S.enrollIndex=Math.min(S.enrollPhrases.length-1,(S.enrollIndex||0)+1);render()},enrollSubmit:submitEnrollment};if(actions[target.dataset.action])await actions[target.dataset.action]()}catch(err){toast(err.message);log(err.message)}});
document.addEventListener('change',async e=>{try{if(e.target.id==='demo-voice')S.demoVoice=e.target.value;if(['probe-file','analysis-file'].includes(e.target.id))await loadAudio(e.target.files[0]);if(e.target.id==='speaker'){S.challenge=null;S.challengeUser=e.target.value;clearAudio();releaseMic();render();await loadReference(S.challengeUser)}}catch(err){toast('Audio could not be loaded: '+err.message)}});
document.addEventListener('input',e=>{if(e.target.id==='enroll-name')S.enrollUsername=e.target.value.trim().toLowerCase()});
document.addEventListener('submit',async e=>{e.preventDefault();if(e.target.id==='enroll-form')await enroll(e.target);if(e.target.id==='settings-form'){const value=$('#api-base').value.trim().replace(/\/$/,'');if(value&&!/^https?:\/\//.test(value)){toast('Enter an HTTP or HTTPS URL.');return}S.api=value;localStorage.setItem('voiceguard-api',value);await refresh()}});
window.addEventListener('hashchange',()=>{if(S.recording){stopRecording()}else releaseMic();S.page=pages.some(p=>p[0]===location.hash.slice(1))?location.hash.slice(1):'dashboard';render();window.scrollTo(0,0)});
window.addEventListener('resize',()=>{drawWave();drawComparison();drawEvidence();drawSpectrogram()});window.addEventListener('beforeunload',releaseMic);$('#refresh').onclick=refresh;S.page=pages.some(p=>p[0]===location.hash.slice(1))?location.hash.slice(1):'dashboard';render();refresh();

function signalRegions(buffer){
  if(!buffer)return [];
  const d=buffer.getChannelData(0),size=Math.max(1,Math.round(buffer.sampleRate*.1)),regions=[];
  for(let a=0;a<d.length;a+=size){const end=Math.min(d.length,a+size);let sum=0,peak=0;for(let i=a;i<end;i++){sum+=d[i]*d[i];peak=Math.max(peak,Math.abs(d[i]))}
    const kind=peak>=.99?'clipping':Math.sqrt(sum/(end-a))<.003?'low energy':null;
    if(kind){const last=regions[regions.length-1];if(last&&last.kind===kind&&last.end===a/buffer.sampleRate)last.end=end/buffer.sampleRate;else regions.push({kind,start:a/buffer.sampleRate,end:end/buffer.sampleRate})}
  }return regions;
}
function comparison(){return `<div class="signal-workspace"><div class="signal-heading"><span>Peak-normalized amplitude</span><span class="signal-key"><i class="reference-dot"></i>Reference <i class="probe-dot"></i>Live response</span></div><div class="signal-pair"><div class="signal-track"><div class="track-label"><b>01</b><div><h3>Reference voice</h3><small>${esc(S.referenceUser||S.challengeUser||'Select an identity')}</small></div></div><canvas id="reference-wave" class="precision-wave" aria-label="Enrolled reference waveform"></canvas>${!S.reference?`<div class="track-empty">${esc(S.referenceMessage)}</div>`:''}<span class="axis-label">Time (seconds)</span></div><div class="signal-track"><div class="track-label"><b>02</b><div><h3>Live recording</h3><small>${S.buffer?S.buffer.duration.toFixed(2)+' seconds':S.recording?'Recording…':'Awaiting audio'}</small></div></div><canvas id="probe-wave" class="precision-wave" aria-label="Live waveform with highlighted audio quality regions"></canvas>${!S.buffer&&!S.recording?'<div class="track-empty">Your recording appears here.</div>':''}<span class="axis-label">Time (seconds)</span></div></div><div class="signal-legend"><span><i class="quiet-dot"></i>Low-energy region</span><span><i class="clip-dot"></i>Clipping</span><span>Shared time scale · independent display gain</span></div>${S.buffer?`<div class="region-list">${signalRegions(S.buffer).slice(0,8).map(r=>`<button class="region-chip" data-region-start="${r.start}" data-region-end="${r.end}" title="Inspect this interval on both plots">${r.start.toFixed(2)}–${r.end.toFixed(2)}s <span>${r.kind}</span></button>`).join('')||'<span class="pill green">No signal-quality flags</span>'}</div>`:''}<p class="signal-caption">Shading shows measured audio-quality flags. Select an interval to highlight it on both plots. Different phrases have different wave shapes; model decisions apply to the full recording.</p></div>`}
function paintSignal(canvas,buffer,color,highlight=false,sharedDuration=null){
 if(!canvas)return;const ratio=window.devicePixelRatio||1,w=Math.max(1,canvas.clientWidth),h=canvas.clientHeight||240;
 canvas._signalHover={buffer,regions:buffer?signalRegions(buffer):[],duration:sharedDuration||buffer?.duration||5,left:35,right:w-10};canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);const c=canvas.getContext('2d');c.clearRect(0,0,canvas.width,canvas.height);
 const px=x=>x*ratio,left=35,right=w-10,top=20,bottom=h-28,mid=(top+bottom)/2,amp=(bottom-top)/2,plotWidth=Math.max(1,right-left);
 const duration=sharedDuration||buffer?.duration||5;
 c.strokeStyle='#e8edf5';c.lineWidth=ratio;
 for(const v of [-1,-.5,0,.5,1]){const y=mid-v*amp;c.beginPath();c.moveTo(px(left),px(y));c.lineTo(px(right),px(y));c.stroke();if(c.fillText){c.fillStyle='#607086';c.font=`600 ${11*ratio}px sans-serif`;c.fillText(v.toFixed(1),px(2),px(y+3))}}
 for(let i=0;i<=4;i++){const x=left+i*plotWidth/4;c.beginPath();c.moveTo(px(x),px(top));c.lineTo(px(x),px(bottom));c.stroke();if(c.fillText){c.fillStyle='#607086';c.fillText((duration*i/4).toFixed(1),px(x-6),px(h-7))}}
 if(S.selectedRegion&&c.fillRect){c.fillStyle='#f2bc6840';c.fillRect(px(left+S.selectedRegion.start/duration*plotWidth),px(top),px((S.selectedRegion.end-S.selectedRegion.start)/duration*plotWidth),px(bottom-top))}
 if(!buffer)return;const data=buffer.getChannelData(0);let peak=0;for(let i=0;i<data.length;i++)peak=Math.max(peak,Math.abs(data[i]));const gain=peak>1e-4?.95/peak:1;
 if(highlight&&c.fillRect)for(const r of signalRegions(buffer)){c.fillStyle=r.kind==='clipping'?'#ef718b30':'#efb95f30';c.fillRect(px(left+r.start/duration*plotWidth),px(top),px((r.end-r.start)/duration*plotWidth),px(bottom-top))}
 c.strokeStyle=color;c.lineWidth=1.1*ratio;c.beginPath();const activeWidth=Math.min(plotWidth,plotWidth*buffer.duration/duration);
 for(let x=0;x<activeWidth;x++){const a=Math.floor(x/activeWidth*data.length),b=Math.max(a+1,Math.floor((x+1)/activeWidth*data.length));let lo=1,hi=-1;for(let i=a;i<Math.min(b,data.length);i++){lo=Math.min(lo,data[i]);hi=Math.max(hi,data[i])}c.moveTo(px(left+x),px(mid-hi*gain*amp));c.lineTo(px(left+x),px(mid-lo*gain*amp))}c.stroke();
}
function drawWave(){let buffer=S.buffer;if(S.recording&&chunks.length){const d=chunks[chunks.length-1];buffer={sampleRate:context.sampleRate,duration:d.length/context.sampleRate,getChannelData:()=>d}}paintSignal($('#waveform'),buffer,'#5774ec',true)}
function drawComparison(){let probe=S.buffer;if(S.recording&&chunks.length){const d=chunks[chunks.length-1];probe={sampleRate:context.sampleRate,duration:d.length/context.sampleRate,getChannelData:()=>d}}const duration=Math.max(S.reference?.duration||0,probe?.duration||0,1);paintSignal($('#reference-wave'),S.reference,'#7277db',false,duration);paintSignal($('#probe-wave'),probe,'#199caa',true,duration)}
async function loadReference(username){
 S.reference=null;S.referenceUser=username;S.referenceMessage=username?'Loading enrolled reference…':'Select a speaker to load their enrolled reference.';render();if(!username)return;
 try{const res=await fetch(`${S.api}/api/v1/users/${encodeURIComponent(username)}/reference`,{signal:AbortSignal.timeout(15000)});if(!res.ok){const data=await res.json();throw Error(data.detail||'Reference unavailable')}
 if(!context)context=new AudioContext();const buffer=await context.decodeAudioData(await res.arrayBuffer());if(S.challengeUser!==username)return;S.reference=buffer;S.referenceMessage='';
 }catch(e){if(S.challengeUser!==username)return;S.referenceMessage=e.message}render();
}

function challengeSummary(r){const ch=r.challenge_status;if(!ch)return '';return `<div class="challenge-summary"><h3>Spoken challenge <span class="pill ${ch.passed?'green':'red'}">${ch.passed?'Passed':'Did not pass'}</span></h3>${ch.target_phrase?`<p>Expected: ${ch.target_phrase.split(' ').map(word=>`<mark class="${(ch.missing_words||[]).includes(word)?'missing-token':'matched-token'}">${esc(word)}</mark>`).join(' ')}</p>`:''}<p>Recognized: ${esc(ch.transcription||'No transcript available')}</p><p>${esc(ch.reason||'')}</p>${r.telemetry?.total_latency_ms!==undefined?`<p>Processing time: ${(r.telemetry.total_latency_ms/1000).toFixed(2)} seconds</p>`:''}</div>`}

async function encodeCapture(samples,rate){
 if(rate===16000)return wav(samples,16000);
 // Use the browser's filtered resampler instead of box averaging, which
 // folds frequencies above 8 kHz into the anti-spoof model's input band.
 const offline=new OfflineAudioContext(1,Math.max(1,Math.round(samples.length*16000/rate)),16000);
 const buffer=offline.createBuffer(1,samples.length,rate);buffer.copyToChannel(samples,0);
 const input=offline.createBufferSource();input.buffer=buffer;input.connect(offline.destination);input.start();
 const rendered=await offline.startRendering();return wav(rendered.getChannelData(0),16000);
}

function aiDemoSection(){return `<section class="card ai-demo"><div class="ai-demo-copy"><span class="eyebrow">SYNTHETIC VOICE DEMO</span><h2>Test With AI</h2><p>Hear a computer-generated version of the current challenge, then test it against your enrolled identity.</p><small>Generic Windows text-to-speech voice · not a clone of the enrolled speaker</small></div><div class="ai-demo-controls"><label for="demo-voice">Agent voice</label><select id="demo-voice" ${S.busy?'disabled':''}>${['default','female','male'].map(v=>`<option value="${v}" ${S.demoVoice===v?'selected':''}>${v==='default'?'Default voice':v==='female'?'Female voice':'Male voice'}</option>`).join('')}</select>${button(S.busy?'Working…':'Generate demo audio','ai','','wave')}<span class="subtle">${S.syntheticSource?'Synthetic audio loaded. Listen above, then Verify identity.':'A fresh challenge is required. All verification gates stay active.'}</span></div></section>`}
async function generateDemoVoice(){
 if(S.busy)return;if(S.recording)throw Error('Stop recording before generating demo audio.');
 if(!S.challenge||S.challenge.expires_at<=Date.now()/1000)await challenge(false);
 const voice=S.demoVoice||'default';S.busy=true;S.error='';render();
 try{const res=await fetch(`${S.api}/api/v1/demo-voice`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:S.challengeUser,session_id:S.challenge.session_id,voice}),signal:AbortSignal.timeout(30000)});
 if(!res.ok){const data=await res.json();throw Error(data.detail||'Demo voice could not be generated.')}
 const blob=await res.blob();blob.name='synthetic-agent-response.wav';await loadAudio(blob,false);S.syntheticSource=true;S.name='Synthetic agent · '+voice;await persistRecording();log('Generated generic synthetic challenge response.');
 }finally{S.busy=false;render()}
}
function thresholdChart(value,threshold,kind){
 if(!Number.isFinite(value)||value===-999||!Number.isFinite(threshold))return '<p class="evidence-note">This check was not evaluated.</p>';
 let lo=kind==='speaker'?-1:Math.min(-10,value-2,threshold-2),hi=kind==='speaker'?1:Math.max(10,value+2,threshold+2);
 const x=v=>50+(v-lo)/(hi-lo)*570,a=x(threshold),b=x(value),color=value>=threshold?'#199caa':'#cf526f';
 return `<svg data-hover-kind="threshold" data-score="${value}" data-threshold="${threshold}" class="threshold-chart" viewBox="0 0 680 106" role="img" aria-label="Score ${value.toFixed(4)} compared with required threshold ${threshold.toFixed(4)}"><line x1="50" x2="620" y1="50" y2="50" stroke="#e6eaf3" stroke-width="7"/><line x1="${Math.min(a,b)}" x2="${Math.max(a,b)}" y1="50" y2="50" stroke="${color}" stroke-width="7"/><line x1="${a}" x2="${a}" y1="30" y2="69" stroke="#9299b1" stroke-dasharray="3 3"/><circle cx="${b}" cy="50" r="6" fill="${color}"/><text x="${b}" y="23" text-anchor="middle" fill="${color}">Your score ${value.toFixed(4)}</text><text x="${a}" y="90" text-anchor="middle" fill="#9299b1">Required ${threshold.toFixed(4)}</text></svg>`
}
function featureChart(reference,probe){
 if(!Array.isArray(reference)||!Array.isArray(probe)||reference.length!==probe.length||!reference.length)return '<p class="evidence-note">Feature evidence will appear with your next verification.</p>';
 const n=reference.length,extent=Math.max(.1,...reference.map(Math.abs),...probe.map(Math.abs)),x=i=>45+i/(n-1||1)*585,y=v=>105-v/extent*75;
 const path=values=>values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
 const differences=probe.map((v,i)=>({i,d:reference[i]*(reference[i]-v)})).sort((a,b)=>b.d-a.d).slice(0,5);
 return `<svg data-hover-kind="features" class="feature-chart" viewBox="0 0 680 225" role="img" aria-label="Reference and recorded speaker feature curves"><line x1="45" x2="630" y1="105" y2="105" stroke="#e6eaf3"/>${differences.map(({i})=>`<rect x="${x(i)-2}" y="26" width="4" height="158" fill="#efb95f45"/>`).join('')}<path d="${path(reference)}" fill="none" stroke="#7277db" stroke-width="1.3"/><path d="${path(probe)}" fill="none" stroke="#199caa" stroke-width="1.3"/><text x="45" y="210">Feature 0</text><text x="555" y="210">Feature ${n-1}</text></svg><p class="evidence-note">Violet: enrolled voiceprint. Teal: response. Amber: the five greatest reductions from a reference self-match. These explain feature-level similarity loss, not audio timestamps. The reference curve is the enrolled template; its waveform preview is one enrollment recording.</p>`
}
function fusionChart(f){
 if(!f||![f.speaker_contribution,f.countermeasure_contribution,f.bias].every(Number.isFinite))return '<p class="evidence-note">Fusion breakdown will appear with your next verification.</p>';
 const terms=[f.bias,f.speaker_contribution,f.countermeasure_contribution],values=[terms[0],terms[0]+terms[1],terms.reduce((a,b)=>a+b,0)],lo=Math.min(0,...values)-1,hi=Math.max(0,...values)+1,y=v=>145-(v-lo)/(hi-lo)*110;
 return `<svg data-hover-kind="fusion" class="fusion-chart" viewBox="0 0 680 205" role="img" aria-label="Measured contributions to the fused decision score"><line x1="60" x2="620" y1="${y(0)}" y2="${y(0)}" stroke="#e6eaf3"/><path d="M100,${y(values[0])} L340,${y(values[1])} L580,${y(values[2])}" fill="none" stroke="#7277db" stroke-width="2"/>${values.map((v,i)=>`<circle cx="${100+i*240}" cy="${y(v)}" r="5" fill="${terms[i]<0?'#cf526f':'#199caa'}"/><text x="${100+i*240}" y="${y(v)-12}" text-anchor="middle">${v.toFixed(4)}</text>`).join('')}<text x="100" y="182" text-anchor="middle">Bias ${terms[0].toFixed(3)}</text><text x="340" y="182" text-anchor="middle">+ Speaker ${terms[1].toFixed(3)}</text><text x="580" y="182" text-anchor="middle">+ Anti-spoof ${terms[2].toFixed(3)}</text></svg>`
}
function evidencePanels(r){
 const e=r.evidence||{},rows=[['speaker','Speaker similarity',r.speaker_score,r.speaker_threshold],['countermeasure','Anti-spoof score',r.spoof_score,r.spoof_threshold],['fusion','Fused decision score',r.fused_score,r.fusion_threshold]];
 return `<div class="evidence-stack"><h3>Explore the verification evidence</h3>${r.source_type==='synthetic_demo'?`<div class="info ${r.decision==='ACCESS_GRANTED'?'danger-note':''}">Synthetic demo result. ${r.decision==='ACCESS_GRANTED'?'The system accepted this synthetic sample; this demonstrates a weakness, not successful human authentication.':'Review which checks rejected this generic generated voice.'}</div>`:''}${rows.map(([key,title,value,threshold],i)=>{const done=Number.isFinite(value)&&value!==-999,pass=done&&value>=threshold;return `<details class="evidence-panel" data-evidence="${key}"><summary><span class="evidence-index">0${i+1}</span><b>${title}</b><span class="pill ${done?pass?'green':'red':'gray'}">${done?pass?'Threshold met':'Below threshold':'Not evaluated'}</span><span class="expand-sign">+</span></summary><div class="evidence-body"><h4>Score versus required standard</h4>${thresholdChart(value,threshold,key)}${key==='speaker'?`<h4>Reference versus recorded audio</h4>${evidenceWavePair(key)}<h4 style="margin-top:22px">Enrolled voiceprint versus response</h4>${featureChart(e.speaker?.reference_embedding,e.speaker?.probe_embedding)}<ul><li>The model compares voiceprint features, not raw wave shapes.</li><li>${done?`Similarity ${value.toFixed(4)} ${pass?'meets':'falls below'} the ${threshold.toFixed(4)} minimum.`:'This check did not run because an earlier verification stage stopped.'}</li></ul>`:key==='countermeasure'?`${Number.isFinite(e.countermeasure?.bona_fide_logit)&&Number.isFinite(e.countermeasure?.spoof_logit)?`<div class="score-formula">Bona fide logit ${e.countermeasure.bona_fide_logit.toFixed(4)} − spoof logit ${e.countermeasure.spoof_logit.toFixed(4)} = anti-spoof score ${value.toFixed(4)}</div>`:''}<h4>Reference and analyzed recording</h4>${evidenceWavePair(key)}<ul><li>${done?`Anti-spoof score ${value.toFixed(4)} ${pass?'meets':'falls below'} the required ${threshold.toFixed(4)}.`:'The countermeasure did not run.'}</li><li>Shading marks low energy or clipping; the model does not produce a spoof timestamp.</li>${e.countermeasure?`<li>AASIST used 0–${e.countermeasure.input_end_seconds.toFixed(2)}s.${e.countermeasure.short_clip_repeated?' The short clip was repeated to fill its model window.':''}</li>`:''}</ul>`:`<h4>How the final score is built</h4>${fusionChart(e.fusion)}${e.fusion?`<div class="score-formula">Speaker weight ${e.fusion.speaker_weight?.toFixed(4)||'not reported'} · Anti-spoof weight ${e.fusion.countermeasure_weight?.toFixed(4)||'not reported'} · Bias ${e.fusion.bias.toFixed(4)}</div>`:''}<h4 style="margin-top:22px">Audio used for this decision</h4>${evidenceWavePair(key)}<ul><li>Fusion combines weighted speaker similarity, anti-spoof score, and a bias.</li><li>${e.fusion?.require_cm_gate?'The mandatory anti-spoof gate must also pass, even when fusion is above its threshold.':'The server policy determines which additional gates are required.'}</li><li>Red points show negative score contributions, not localized audio defects.</li></ul>`}</div></details>`}).join('')}</div>`
}
function evidenceWavePair(key){return `<div class="signal-pair evidence-wave-pair"><div class="signal-track"><h3>Reference voice</h3><canvas id="${key}-reference" class="precision-wave" aria-label="Reference audio in ${key} evidence"></canvas>${!S.reference?'<p class="evidence-note">Reference audio unavailable.</p>':''}</div><div class="signal-track"><h3>Recorded response</h3><canvas id="${key}-probe" class="precision-wave" aria-label="Recorded audio with measured quality flags"></canvas></div></div>`}
function drawEvidence(){const audio=S.result?.audioSnapshot||S;const duration=Math.max(audio.reference?.duration||0,audio.buffer?.duration||0,1);for(const key of ['speaker','countermeasure','fusion']){paintSignal($('#'+key+'-reference'),audio.reference,'#7277db',false,duration);paintSignal($('#'+key+'-probe'),audio.buffer,'#199caa',true,duration)}}
document.addEventListener('toggle',e=>{if(e.target.matches?.('.evidence-panel')&&e.target.open)drawEvidence()},true);

async function reloadRecordingHistory(){try{S.recordings=(await api('/api/v1/recordings')).recordings||[]}catch(e){log('Recording history: '+e.message)}}
async function persistRecording(){if(!S.blob)return;const data=new FormData();data.append('username',S.challengeUser||'unassigned');data.append('name',S.name||'Recording');data.append('source_type',S.syntheticSource?'synthetic_demo':'microphone_or_upload');data.append('audio_file',S.blob,'recording.wav');try{const item=await api('/api/v1/recordings',{method:'POST',body:data});S.recordingId=item.id;await reloadRecordingHistory()}catch(e){toast('Recording could not be saved: '+e.message)}}
function recordingTable(){return S.recordings.length?`<div class="table-wrap"><table><thead><tr><th>RECORDING</th><th>SPEAKER</th><th>RESULT</th><th>RECORDED</th><th></th></tr></thead><tbody>${S.recordings.map(i=>`<tr><td><b>${esc(i.name)}</b><br><small>${esc(i.source_type)}</small></td><td>${esc(i.username)}</td><td><span class="pill ${i.result?i.result.decision==='ACCESS_GRANTED'?'green':'red':'gray'}">${i.result?i.result.decision==='ACCESS_GRANTED'?'Granted':'Denied':i.archived_decision?i.archived_decision==='ACCESS_GRANTED'?'Granted (archive)':'Denied (archive)':'Not verified'}</span></td><td>${esc(new Date(i.created_at).toLocaleString())}</td><td><button class="button" data-recording="${esc(i.id)}">Open audio & evidence</button></td></tr>`).join('')}</tbody></table></div>`:empty('No saved recordings yet.')}
async function openSavedRecording(id){const item=S.recordings.find(i=>i.id===id);if(!item)return;const response=await fetch(`${S.api}/api/v1/recordings/${id}/audio`);if(!response.ok)throw Error('Saved audio is unavailable.');const blob=await response.blob();blob.name=item.name;await loadAudio(blob,false);S.recordingId=id;S.challenge=null;S.challengeUser=item.username;S.reference=null;S.referenceUser=item.username+(item.reference_origin?' · reference at import':'');S.syntheticSource=item.source_type==='synthetic_demo';try{const ref=await fetch(`${S.api}/api/v1/recordings/${id}/reference`);if(ref.ok)S.reference=await context.decodeAudioData(await ref.arrayBuffer())}catch{}S.result=item.result?{...item.result}:null;if(S.result)Object.defineProperty(S.result,'audioSnapshot',{value:{buffer:S.buffer,reference:S.reference,referenceUser:S.referenceUser,blob:S.blob,name:item.name}});S.page=S.result?'results':'analysis';location.hash=S.page;render()}
document.addEventListener('pointermove',e=>{const graph=e.target.closest('canvas,svg[data-hover-kind]'),tip=$('#graph-tooltip');if(!tip)return;if(!graph){tip.hidden=true;return}const rect=graph.getBoundingClientRect();let message='';if(graph._signalHover?.buffer){const a=graph._signalHover,t=Math.max(0,Math.min(a.duration,(e.clientX-rect.left-a.left)/Math.max(1,a.right-a.left)*a.duration)),b=a.buffer;if(t<=b.duration){const d=b.getChannelData(0),i=Math.min(d.length-1,Math.floor(t*b.sampleRate));message=`Time ${t.toFixed(3)} s\nRaw amplitude ${d[i].toFixed(5)}\n${a.regions.find(r=>t>=r.start&&t<r.end)?.kind||'No quality flag at this point'}`}}else if(graph.dataset.hoverKind==='threshold'){message=`Score ${Number(graph.dataset.score).toFixed(4)}\nRequired threshold ${Number(graph.dataset.threshold).toFixed(4)}\nMargin ${(Number(graph.dataset.score)-Number(graph.dataset.threshold)).toFixed(4)}`}else if(graph.dataset.hoverKind==='features'){const f=S.result?.evidence?.speaker;if(f){const i=Math.max(0,Math.min(f.probe_embedding.length-1,Math.round(((e.clientX-rect.left)/rect.width*680-45)/585*(f.probe_embedding.length-1))));message=`Feature ${i}\nReference ${f.reference_embedding[i].toFixed(5)}\nResponse ${f.probe_embedding[i].toFixed(5)}\nSimilarity contribution ${(f.reference_embedding[i]*f.probe_embedding[i]).toFixed(5)}`}}else if(graph.dataset.hoverKind==='fusion'){const f=S.result?.evidence?.fusion;if(f){const i=Math.max(0,Math.min(2,Math.round(((e.clientX-rect.left)/rect.width*680-100)/240))),v=[f.bias,f.bias+f.speaker_contribution,f.bias+f.speaker_contribution+f.countermeasure_contribution];message=`${['Bias','After speaker contribution','Final fused score'][i]}\nScore ${v[i].toFixed(4)}`}}tip.textContent=message;tip.hidden=!message;tip.style.left=Math.min(e.clientX+14,window.innerWidth-250)+'px';tip.style.top=Math.max(8,Math.min(e.clientY+14,window.innerHeight-100))+'px'});
document.addEventListener('pointerleave',()=>{const tip=$('#graph-tooltip');if(tip)tip.hidden=true});
