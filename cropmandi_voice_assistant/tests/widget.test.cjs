/* Deterministic widget lifecycle tests; no browser, microphone or network required. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/js/voice-assistant.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; }
function harness(options={}) {
  const elements = {}, page = {}, timers = new Map(), calls = [], storage = new Map(); let timerId = 0, players = 0;
  class Element {
    constructor(id) {this.id=id;this.value='';this.textContent='';this.disabled=false;this.children=[];this.handlers={};this.hidden=id==='cmVoicePanel';this.attrs={};this.classList={add(){},remove(){}};}
    addEventListener(name,fn) {this.handlers[name]=fn;}
    setAttribute(k,v) {this.attrs[k]=v;}
    appendChild(el) {this.children.push(el);el.parent=this;}
    replaceChildren() {this.children=[];}
    focus() {}
    remove() {this.parent.children.splice(this.parent.children.indexOf(this),1);}
    querySelector(selector) {return elements[selector.slice(1)] ||= new Element(selector.slice(1));}
    get firstElementChild() {return this.children[0];}
  }
  const document = {body:new Element('body'),createElement:() => new Element(),getElementById:id => page['#'+id] || null,querySelector:sel => page[sel] || null,addEventListener(){}};
  const location = {pathname:'/cropmandi_ai_harvest_route/code.html',hash:'',href:'http://localhost:8766/cropmandi_ai_harvest_route/code.html',origin:'http://localhost:8766',assign(url){this.assigned=url;}};
  const sessionStorage = {getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
  const window = {location,CropMandiVoiceConfig:{autoSpeak:!!options.audio},sessionStorage,
    setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,delay});return id;},clearTimeout(id){timers.delete(id);},addEventListener(){},dispatchEvent(){}};
  const response = data => ({ok:true,json:async()=>({success:true,data})});
  const fetch = async (url,opts) => {
    calls.push({url,opts});
    if (opts.signal?.aborted) throw new DOMException('aborted','AbortError');
    if (options.fetch) return options.fetch(url,opts,response);
    return response({answer:'Recorded answer',language:'en',conversation:{commodity:'tomato',market:'Kolar'}});
  };
  const navigator = {mediaDevices:options.mediaDevices};
  function Audio() {players++;this.pause=()=>{};this.play=async()=>{};}
  const context={window,document,navigator,sessionStorage,fetch,AbortController,AbortSignal,DOMException,URL,Blob,FormData,Date,CustomEvent:class{},Audio,MediaRecorder:options.MediaRecorder};
  vm.runInNewContext(source,context);
  elements.cmVoiceLanguage.value='en-IN';
  return {voice:window.CropMandiVoice,elements,page,timers,calls,location,response,players:()=>players,
    click(id){return elements[id].handlers.click();},
    flush(delay){for(const [id,t] of timers) if(t.delay===delay){timers.delete(id);t.fn();}}};
}

test('follow-up does not reintroduce page coffee variety after spoken crop change',async()=>{
  const h=harness();h.page['#commodity']={value:'coffee'};h.page['#series']={value:'ARABICA PARCHMENT'};
  await h.voice.send('tomato price at Kolar');await h.voice.send('predict tomorrow');
  const body=JSON.parse(h.calls[1].opts.body);
  assert.equal(body.context.commodity,'tomato');assert.equal(body.context.variety,undefined);
});
test('changed page selection supersedes conversation selections',async()=>{
  const h=harness();h.page['#commodity']={value:'coffee'};await h.voice.send('tomato price');
  h.page['#commodity'].value='maize';await h.voice.send('latest price');
  assert.equal(JSON.parse(h.calls[1].opts.body).context.commodity,'maize');
});
test('identical in-flight commands are suppressed and close cancels stale response',async()=>{
  const wait=deferred();const h=harness({fetch:()=>wait.promise});const first=h.voice.send('price');
  await h.voice.send('price');assert.equal(h.calls.length,1);h.voice.close();
  wait.resolve(h.response({answer:'stale',language:'en'}));await first;
  assert.equal(h.elements.cmVoiceMessages.children.filter(x=>x.textContent==='stale').length,0);
});
test('a new command supersedes an older pending command',async()=>{
  const wait=deferred();const h=harness({fetch:(_url,_opts,response)=>h.calls.length===1?wait.promise:response({answer:'new',language:'en',conversation:{}})});
  const first=h.voice.send('first');await h.voice.send('second');
  wait.resolve(h.response({answer:'old',language:'en'}));await first;
  assert.equal(h.calls[0].opts.signal.aborted,true);
  assert.equal(h.elements.cmVoiceMessages.children.filter(x=>x.textContent==='old').length,0);
});
test('stopping pending synthesis prevents late audio playback',async()=>{
  const wait=deferred();const h=harness({audio:true,fetch:(url,_opts,response)=>url.endsWith('/speak')?wait.promise:response({answer:'voice',language:'en',conversation:{}})});
  const pending=h.voice.send('hello');await tick();h.voice.stopSpeaking();
  wait.resolve({ok:true,blob:async()=>new Blob(['audio'])});await pending;
  assert.equal(h.players(),0);assert.equal(h.elements.cmVoiceStop.disabled,true);
});
test('network timeout clears processing state',async()=>{
  const h=harness({fetch:(_url,opts)=>new Promise((_resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(new DOMException('timeout','AbortError'))))});
  const pending=h.voice.send('price');h.flush(45000);await pending;
  assert.equal(h.elements.cmVoiceStatus.textContent,'Ready to help');
  assert.match(h.elements.cmVoiceMessages.children.at(-1).textContent,/failed or timed out/);
});
test('microphone denial restores controls',async()=>{
  const h=harness({mediaDevices:{getUserMedia:async()=>{throw new DOMException('denied','NotAllowedError');}},MediaRecorder:function(){}});
  h.click('cmVoiceMic');await tick();assert.equal(h.elements.cmVoiceMic.disabled,false);
  assert.match(h.elements.cmVoiceMessages.children.at(-1).textContent,/permission denied/);
});
test('late microphone permission after close releases tracks',async()=>{
  let stopped=0;const wait=deferred();const h=harness({mediaDevices:{getUserMedia:()=>wait.promise},MediaRecorder:function(){}});
  h.click('cmVoiceMic');h.voice.close();wait.resolve({getTracks:()=>[{stop(){stopped++;}}]});await tick();
  assert.equal(stopped,1);assert.equal(h.elements.cmVoiceMic.disabled,false);
});
test('pending microphone permission expires without stuck listening',async()=>{
  const h=harness({mediaDevices:{getUserMedia:()=>new Promise(()=>{})},MediaRecorder:function(){}});
  h.click('cmVoiceMic');h.flush(15000);assert.equal(h.elements.cmVoiceMic.disabled,false);
  assert.equal(h.elements.cmVoiceStatus.textContent,'Ready to help');
});
test('unknown navigation never leaves the application',async()=>{
  const h=harness({fetch:(_url,_opts,response)=>response({answer:'navigate',language:'en',conversation:{},action:{type:'navigate',path:'https://example.com'}})});
  await h.voice.send('open');assert.equal(h.location.assigned,undefined);assert.equal(h.calls.length,1);
});
test('standalone and integrated widget assets remain identical',()=>{
  assert.equal(source,fs.readFileSync(path.join(__dirname,'../static/voice-assistant.js'),'utf8'));
});

test('HarvestRoute JSON series selections preserve variety and grade',()=>{
  const h=harness();h.page['#commodity']={value:'maize'};h.page['#series']={value:'["HYBRID/LOCAL", "SMALL"]'};
  const context=h.voice.getContext();assert.equal(context.variety,'HYBRID/LOCAL');assert.equal(context.grade,'SMALL');assert.equal(context.quantity_unit,'kg');
});
test('uncertain transcript is editable and never auto-executes a command',async()=>{
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(){this.state='inactive';this.mimeType='audio/webm';}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable({data:new Blob(['clip'])});this.onstop();}
  }
  let stopped=0;
  const h=harness({MediaRecorder:Recorder,mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){stopped++;}}]})},fetch:(_url,_opts,response)=>response({text:'uncertain transcript',detected_language:'kn',language_probability:1,needs_confirmation:true})});
  h.click('cmVoiceMic');await tick();h.flush(30000);await tick();
  assert.equal(h.elements.cmVoiceText.value,'uncertain transcript');assert.equal(stopped,1);
  assert.equal(h.calls.filter(c=>c.url.endsWith('/command')).length,0);
  assert.equal(h.elements.cmVoiceMic.disabled,false);
});

test('unsupported microphone clears a previously pending processing state',async()=>{
  const wait=deferred();const h=harness({fetch:()=>wait.promise});const first=h.voice.send('price');
  h.click('cmVoiceMic');assert.equal(h.elements.cmVoiceStatus.textContent,'Ready to help');
  wait.resolve(h.response({answer:'stale',language:'en'}));await first;
  assert.match(h.elements.cmVoiceMessages.children.at(-1).textContent,/supported browser/);
});

test('uncertain transcript review is spoken and replayable in Kannada',async()=>{
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(){this.state='inactive';this.mimeType='audio/webm';}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable({data:new Blob(['clip'])});this.onstop();}
  }
  const wait=deferred();
  const h=harness({audio:true,MediaRecorder:Recorder,mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}]})},fetch:(url,_opts,response)=>url.endsWith('/speak')?wait.promise:response({text:'uncertain Kannada',detected_language:'kn',language_probability:1,needs_confirmation:true})});
  h.elements.cmVoiceLanguage.value='kn-IN';h.click('cmVoiceMic');await tick();h.flush(30000);await tick();
  const calls=h.calls.filter(c=>c.url.endsWith('/speak'));assert.equal(calls.length,1);
  assert.equal(JSON.parse(calls[0].opts.body).language,'kn-IN');assert.match(JSON.parse(calls[0].opts.body).text,/ಲಿಪ್ಯಂತರಣ/);
  assert.equal(h.elements.cmVoiceReplay.disabled,false);assert.equal(h.calls.filter(c=>c.url.endsWith('/command')).length,0);
  h.voice.stopSpeaking();wait.resolve({ok:true,blob:async()=>new Blob(['audio'])});await tick();
});
