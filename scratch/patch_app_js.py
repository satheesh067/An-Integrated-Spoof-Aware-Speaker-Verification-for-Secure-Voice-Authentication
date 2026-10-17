import re

with open("frontend/app.js", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update S definition
old_s = "const S={page:'dashboard',online:false,health:null,users:[],history:[],recordings:[],recordingId:null,result:null,challenge:null,challengeUser:null,blob:null,buffer:null,url:null,name:'',recording:false,busy:false,api:localStorage.getItem('voiceguard-api')||'',logs:[],enrollFiles:[],userError:'',syntheticSource:false,demoVoice:'default',error:'',reference:null,referenceUser:null,referenceMessage:'Select a speaker to load their enrolled reference.'};"
new_s = "const S={page:'dashboard',online:false,health:null,users:[],history:[],recordings:[],recordingId:null,result:null,challenge:null,challengeUser:null,blob:null,buffer:null,url:null,name:'',recording:false,busy:false,api:localStorage.getItem('voiceguard-api')||'',logs:[],enrollFiles:[],userError:'',syntheticSource:false,demoVoice:'default',error:'',reference:null,referenceUser:null,referenceMessage:'Select a speaker to load their enrolled reference.',enrollPhrases:['The quick brown fox jumps over the lazy dog near the riverbank.','My voice is my unique biometric passport for secure system access.','VoiceGuard AI verifies genuine identity using neural speech authentication.'],enrollIndex:0,enrollRecordings:[null,null,null],enrollRecording:false,enrollUsername:''};"

assert old_s in content, "old_s not found"
content = content.replace(old_s, new_s)

# 2. Update globals line
old_globals = "let context,processor,source,stream,chunks=[],recordTimer,challengeTimer,recordStarted=0,toastTimer;"
new_globals = "let context,processor,source,stream,chunks=[],recordTimer,challengeTimer,recordStarted=0,toastTimer,enrollProcessor,enrollSource,enrollChunks=[],enrollTimer,enrollStarted=0;"

assert old_globals in content, "old_globals not found"
content = content.replace(old_globals, new_globals)

# 3. Update releaseMic
old_release = "function releaseMic(){stream?.getTracks().forEach(t=>t.stop());stream=null;source?.disconnect();processor?.disconnect();processor=null;source=null}"
new_release = "function releaseMic(){stream?.getTracks().forEach(t=>t.stop());stream=null;source?.disconnect();processor?.disconnect();processor=null;source=null;enrollSource?.disconnect();enrollProcessor?.disconnect();enrollSource=null;enrollProcessor=null}"

assert old_release in content, "old_release not found"
content = content.replace(old_release, new_release)

# 4. Update render to call drawEnrollWave()
old_render_end = "drawComparison();drawWave();drawEvidence();drawSpectrogram();updateTTL()}"
new_render_end = "drawComparison();drawWave();drawEvidence();drawSpectrogram();drawEnrollWave();updateTTL()}"

assert old_render_end in content, "old_render_end not found"
content = content.replace(old_render_end, new_render_end)

# 5. Define new functions for live enrollment
enroll_functions = """
async function startEnrollRecording(){
  if(S.busy)return;
  const nameInput=$('#enroll-name');
  const username=(nameInput?.value||S.enrollUsername||'').trim().toLowerCase();
  if(!username){toast('Please enter a unique speaker ID first.');nameInput?.focus();return}
  if(!/^[a-z0-9_-]{1,64}$/.test(username)){toast('Use letters, numbers, underscores, or hyphens for speaker ID.');nameInput?.focus();return}
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
    if(el)el.textContent=`${elapsed.toFixed(1)}s · Speak the highlighted sentence aloud`;
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
    toast('Recording was too short (< 1.0s). Please speak the complete sentence.');
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
  toast(`Sentence ${idx+1} captured successfully (${buffer.duration.toFixed(1)}s).`);

  if(idx<S.enrollPhrases.length-1&&!S.enrollRecordings[idx+1]){
    S.enrollIndex=idx+1;
  }
  render();
}

function drawEnrollWave(){
  const canvas=$('#enroll-waveform');
  if(!canvas)return;
  let buffer=S.enrollRecordings[S.enrollIndex]?.buffer;
  if(S.enrollRecording&&enrollChunks.length){
    const d=enrollChunks[enrollChunks.length-1];
    buffer={sampleRate:context?.sampleRate||16000,duration:d.length/(context?.sampleRate||16000),getChannelData:()=>d};
  }
  paintSignal(canvas,buffer,S.enrollRecording?'#cf526f':'#6672de',true);
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
"""

# 6. Replace users function
old_users_pattern = re.compile(r"function users\(\)\{return heading\('A voiceprint for every identity\.',.*?8,`<span class=\"pill gray\">\$\{S\.users\.length\} speakers</span>`\)\}\</div\>`\}", re.DOTALL)

# Let's find the exact string of function users
users_start = content.find("function users(){return heading('A voiceprint for every identity.'")
users_end = content.find("function settings(){return heading('Make the workspace yours.'")
assert users_start != -1 and users_end != -1, "users function boundaries not found"

new_users = """function users(){
  const recCount=(S.enrollRecordings||[]).filter(r=>r&&r.blob).length;
  const currentIdx=S.enrollIndex||0;
  const currentPhrase=S.enrollPhrases[currentIdx];
  const currentRec=S.enrollRecordings[currentIdx];
  
  const stepTabs=S.enrollPhrases.map((phrase,idx)=>{
    const isRecorded=!!S.enrollRecordings[idx];
    const isActive=currentIdx===idx;
    return `<button type="button" class="enroll-step-tab ${isActive?'active':''} ${isRecorded?'completed':''}" data-enroll-index="${idx}" ${S.enrollRecording?'disabled':''}>
      <span class="step-num">${isRecorded?'✓':idx+1}</span>
      <span class="step-text">Sentence ${idx+1}</span>
      ${isRecorded?`<span class="step-dur">${S.enrollRecordings[idx].duration.toFixed(1)}s</span>`:''}
    </button>`;
  }).join('');

  const enrollCardHtml=`
    <div class="enroll-container">
      <div class="form-field">
        <label for="enroll-name">Unique speaker ID</label>
        <input id="enroll-name" name="username" required pattern="[a-zA-Z0-9_-]+" maxlength="64" placeholder="e.g. pavan_kumar" value="${esc(S.enrollUsername)}" ${S.enrollRecording||S.busy?'disabled':''}>
        <span class="subtle">Letters, numbers, underscores and hyphens.</span>
      </div>

      <div class="enroll-wizard">
        <div class="wizard-header">
          <span class="eyebrow">STEP 2 · LIVE VOICE ENROLLMENT</span>
          <h3>Read each sentence aloud</h3>
          <p class="subtle">Speak all 3 guided sentences so ECAPA-TDNN captures your complete vocal tract signature with maximum precision.</p>
        </div>

        <div class="enroll-steps-bar">
          ${stepTabs}
        </div>

        <div class="sentence-prompt-card">
          <div class="prompt-header">
            <span class="prompt-badge">SENTENCE ${currentIdx+1} OF 3</span>
            <span class="pill ${currentRec?'green':'gray'}">${currentRec?'Recorded':'Awaiting speech'}</span>
          </div>
          <blockquote class="sentence-text">"${esc(currentPhrase)}"</blockquote>
          <p class="subtle">${currentRec?'Sentence recorded. You can listen below or re-record.':'Read this sentence aloud in your natural speaking voice.'}</p>
        </div>

        <div class="enroll-recorder ${S.enrollRecording?'recording':''}">
          <div class="recorder-status-row">
            <span class="mic-orb ${S.enrollRecording?'pulsing':''}">${icon('mic')}</span>
            <div>
              <h4>${S.enrollRecording?'Recording your voice…':currentRec?'Sentence '+(currentIdx+1)+' captured':'Microphone ready'}</h4>
              <p id="enroll-record-time" class="subtle">${S.enrollRecording?'Speak clearly into the microphone…':currentRec?'Duration: '+currentRec.duration.toFixed(1)+'s · Quality: High':'Click "Start recording" when you are ready to speak.'}</p>
            </div>
          </div>

          <canvas class="wave" id="enroll-waveform" style="height:70px;margin:12px 0;border-radius:8px;background:#fbfcfe"></canvas>

          <div class="recorder-controls" style="margin-top:10px;gap:9px;display:flex;align-items:center;flex-wrap:wrap">
            ${!S.enrollRecording?`
              <button type="button" class="button ${currentRec?'':'primary'}" data-action="enrollRecord">
                ${icon('mic')}${currentRec?'Re-record sentence':'Start recording'}
              </button>
            `:`
              <button type="button" class="button danger" data-action="enrollStop">
                ${icon('stop')}Stop recording
              </button>
            `}
            ${currentRec&&!S.enrollRecording&&currentIdx<2?`
              <button type="button" class="button primary" data-action="enrollNext">
                Next sentence →
              </button>
            `:''}
          </div>

          ${currentRec&&currentRec.url&&!S.enrollRecording?`
            <div style="margin-top:12px">
              <audio controls src="${currentRec.url}"></audio>
            </div>
          `:''}
        </div>

        <div class="enroll-progress-bar-wrap">
          <div class="enroll-progress-text">
            <span><b>${recCount}</b> of 3 sentences recorded</span>
            <span>${recCount===3?'✓ Ready for voiceprint training':'Record all 3 for best precision'}</span>
          </div>
          <div class="enroll-meter">
            <div class="enroll-meter-fill" style="width:${(recCount/3)*100}%"></div>
          </div>
        </div>

        <div class="enroll-submit-row" style="margin-top:18px">
          <button type="button" class="button primary" data-action="enrollSubmit" style="width:100%;padding:14px" ${S.busy||recCount===0?'disabled':''}>
            ${icon('users')}${S.busy?'Extracting embeddings & training…':recCount>=3?'Train & Create Voiceprint (3/3 Ready)':recCount>0?`Train with ${recCount} recording(s)`:'Record sentences to train'}
          </button>
        </div>

        <details class="upload-details" style="margin-top:18px">
          <summary>Or upload audio files manually</summary>
          <label class="upload" style="margin-top:10px">
            ${icon('upload')} Choose WAV files
            <input id="enroll-files" type="file" accept="audio/*" multiple>
          </label>
        </details>
      </div>
    </div>
  `;

  return heading('A voiceprint for every identity.','Enroll genuine speech samples and manage the speaker registry.')+
    `<div class="grid">
      ${card('Enroll a speaker',enrollCardHtml,6)}
      ${card('Speaker registry',S.userError?`<div class="info danger-note">${esc(S.userError)}</div>`:S.users.length?`<div class="table-wrap"><table><thead><tr><th>IDENTITY</th><th>RECORDINGS</th><th>CREATED</th><th></th></tr></thead><tbody>${S.users.map(u=>`<tr><td><b>${esc(u.username)}</b><br><span class="subtle">${esc(u.embedding_dim)} dimensions</span></td><td>${esc(u.num_recordings)}</td><td>${esc(u.created_at?.slice(0,10)||'—')}</td><td><button class="button danger" data-delete="${esc(u.username)}">Delete</button></td></tr>`).join('')}</tbody></table></div>`:empty(S.online?'No speakers enrolled. Create your first voiceprint.':'Connect the backend to load enrolled speakers.','users'),6,`<span class="pill gray">${S.users.length} speakers</span>`)}
    </div>`;
}
"""

content = content[:users_start] + new_users + "\n" + content[users_end:]

# 7. Add helper functions after loadBenchmark
bench_pos = content.find("function exportResult()")
assert bench_pos != -1, "exportResult not found"
content = content[:bench_pos] + enroll_functions + "\n" + content[bench_pos:]

# 8. Update actions object and click listeners in document.addEventListener('click')
old_click_listener = "const actions={challenge,record,ai:generateDemoVoice,stop:stopRecording,verify,clear:()=>{clearAudio();render()},export:exportResult,benchmark:loadBenchmark};"
new_click_listener = """if(target.dataset.enrollIndex!==undefined){S.enrollIndex=Number(target.dataset.enrollIndex);render();return}
    const actions={challenge,record,ai:generateDemoVoice,stop:stopRecording,verify,clear:()=>{clearAudio();render()},export:exportResult,benchmark:loadBenchmark,enrollRecord:startEnrollRecording,enrollStop:stopEnrollRecording,enrollNext:()=>{S.enrollIndex=Math.min(S.enrollPhrases.length-1,(S.enrollIndex||0)+1);render()},enrollSubmit:submitEnrollment};"""

assert old_click_listener in content, "old_click_listener not found"
content = content.replace(old_click_listener, new_click_listener)

# 9. Add input listener for #enroll-name
old_submit_listener = "document.addEventListener('submit',async e=>{"
new_input_and_submit = """document.addEventListener('input',e=>{if(e.target.id==='enroll-name')S.enrollUsername=e.target.value.trim().toLowerCase()});\ndocument.addEventListener('submit',async e=>{"""

assert old_submit_listener in content, "old_submit_listener not found"
content = content.replace(old_submit_listener, new_input_and_submit)

with open("frontend/app.js", "w", encoding="utf-8") as f:
    f.write(content)

print("Updated frontend/app.js successfully!")
