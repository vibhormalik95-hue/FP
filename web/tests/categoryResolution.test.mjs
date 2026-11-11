// Offline component contract harness. Runs real JSX handlers and effects against
// authored API promises; no DOM/browser or live-model validation is claimed.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transformSync} from 'esbuild';

const source=readFileSync(new URL('../src/SemanticPanel.jsx',import.meta.url),'utf8');
const compiled=transformSync(source.replace(/^import React[^\n]+\n/,''),{loader:'jsx',format:'cjs'}).code;
const proposal={label:'Authored preparation candidate',definition:'Explicit bread preparation. Missing facts stay unknown.',rationale:'Authored rationale.',
  evidence:[{item_id:1,field:'caption',quote:'Bread preparation',reason:'Authored evidence.'}]};
const clar={definition_ready:false,resolution_ready:true,resolution_plan_id:'clarify-token',status:'clarify',reason:'Choose a meaning.',objective:'Original objective',
  clarification:{candidate:proposal,model_reason:'Authored rationale.',alternatives:['Serving bread','Preparing other food'],notice:'Unapproved.',question:'Choose the primary or cancel.'},
  provenance:{model_id:'authored',model_revision:'not-model-evidence'},scope_ids:[1,2]};
const review={definition_ready:true,definition_plan_id:'review-token',scope_ids:[1,2],definition:{proposal,objective:'Original objective',
  provenance:clar.provenance,operator_resolution:{choice:'review_primary'},original_clarification:clar}};
const saved={groups:[],feed:{baseline_items:[1,2]},local_models_allowed:false,external_adapter_available:false,category_adapter_available:true,can_undo:false};

function harness(api){
  const slots=[],effects=[];let cursor=0,dirty=false,tree,props={api,user:1,resetKey:0,onFeed:()=>{}};
  function useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;
    return [slots[i],value=>{const next=typeof value==='function'?value(slots[i]):value;if(!Object.is(next,slots[i])){slots[i]=next;dirty=true;}}];}
  function useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i];}
  function useEffect(fn,deps){const i=cursor++;if(!(i in slots)||deps.some((x,n)=>!Object.is(x,slots[i][n]))){slots[i]=deps;effects.push(fn);}}
  const React={createElement:(type,props,...children)=>({type,props:props||{},children}),Fragment:'fragment'};
  const module={exports:{}};
  new Function('React','useState','useRef','useEffect','module','exports',compiled)(React,useState,useRef,useEffect,module,module.exports);
  const Component=module.exports.default;
  function render(){let n=0;do{dirty=false;cursor=0;tree=Component(props);for(const fn of effects.splice(0))fn();if(++n>30)throw Error('Render loop');}while(dirty);return tree;}
  function nodes(node){if(arguments.length===0)node=tree;if(!node||typeof node!=='object')return [];if(Array.isArray(node))return node.flatMap(nodes);return [node,...node.children.flatMap(nodes)];}
  function text(node){if(arguments.length===0)node=tree;if(node==null||typeof node==='boolean')return '';if(typeof node!=='object')return String(node);if(Array.isArray(node))return node.map(text).join(' ');return node.children.map(text).join(' ');}
  function find(fn){const node=nodes().find(fn);assert.ok(node,'Missing node');return node;}
  function button(label){return find(n=>n.type==='button'&&text(n)===label);}
  async function settle(){for(let n=0;n<5;n++){await new Promise(r=>setImmediate(r));render();}}
  async function start(){render();find(n=>n.type==='details').props.onToggle({currentTarget:{open:true}});render();await settle();
    find(n=>n.props.id==='semantic-backend').props.onChange({target:{value:'staged'}});render();
    find(n=>n.props.id==='semantic-text').props.onChange({target:{value:'Original objective'}});render();}
  function changeProps(next){props={...props,...next};render();}
  return {render,find,button,text,nodes,settle,start,changeProps};
}
function fixture(override=()=>undefined){const calls=[];const api=async(path,body)=>{calls.push({path,body});const supplied=override(path,body);if(supplied!==undefined)return supplied;
  if(path.startsWith('semantic/groups'))return structuredClone(saved);
  if(path==='semantic/definition/preview')return structuredClone(clar);
  if(path==='semantic/definition/resolve')return body.choice==='cancel'?{status:'cancelled',definition_ready:false}:structuredClone(review);
  if(path==='semantic/definition/classify')return {ready:false,status:'clarify',reason:'Authored final stop'};
  throw Error('Unexpected API call '+path);};return {calls,ui:harness(api)};}
async function show(ui){await ui.start();ui.button('Propose a definition for review').props.onClick();await ui.settle();}
function choose(ui){ui.find(n=>n.type==='input'&&n.props.name==='category-resolution').props.onChange();ui.render();}

// Labels and disabled state are asserted separately from invoking event handlers.
test('displays exact unapproved candidate, rationale, evidence and nonselectable alternatives without inference',async()=>{
  const {calls,ui}=fixture();await show(ui);
  for(const value of [proposal.label,proposal.definition,proposal.rationale,proposal.evidence[0].quote,...clar.clarification.alternatives])assert.ok(ui.text().includes(value));
  assert.equal(ui.button('Continue to definition review').props.disabled,true);
  assert.equal(ui.nodes().filter(n=>n.type==='input'&&n.props.type==='radio').length,1);
  assert.equal(ui.find(n=>n.props.name==='category-resolution').props.checked,false);
  const before=calls.length;ui.render();ui.render();assert.equal(calls.length,before);
  assert.equal(calls.filter(c=>c.path==='semantic/definition/preview').length,1);
  assert.equal(calls.filter(c=>c.path==='semantic/definition/resolve').length,0);
});

test('explicit primary resolution uses only token and choice, then requires a separate evidence approval',async()=>{
  const {calls,ui}=fixture();await show(ui);
  ui.button('Continue to definition review').props.onClick();await ui.settle();
  assert.equal(calls.filter(c=>c.path==='semantic/definition/resolve').length,0);
  choose(ui);assert.equal(ui.button('Continue to definition review').props.disabled,false);
  ui.button('Continue to definition review').props.onClick();await ui.settle();
  assert.deepEqual(calls.find(c=>c.path==='semantic/definition/resolve').body,{user_id:1,plan_id:'clarify-token',choice:'review_primary'});
  assert.ok(ui.text().includes('original model result remains clarification'));
  assert.equal(ui.button('Approve definition and classify supplied items').props.disabled,true);
  assert.equal(calls.filter(c=>c.path==='semantic/definition/classify').length,0);
  ui.find(n=>n.type==='input'&&n.props.type==='checkbox'&&n.props.checked===false).props.onChange({target:{checked:true}});ui.render();
  ui.button('Approve definition and classify supplied items').props.onClick();await ui.settle();
  assert.deepEqual(calls.find(c=>c.path==='semantic/definition/classify').body,{user_id:1,plan_id:'review-token',evidence_reviewed:true});
  assert.equal(calls.filter(c=>c.path==='semantic/definition/preview').length,1);
});

test('repeated clicks before render send only one preview and one resolution',async()=>{
  let complete;const {calls,ui}=fixture(path=>path==='semantic/definition/resolve'?new Promise(r=>complete=r):undefined);
  await ui.start();const propose=ui.button('Propose a definition for review').props.onClick;propose();propose();await ui.settle();
  assert.equal(calls.filter(c=>c.path==='semantic/definition/preview').length,1);
  choose(ui);const resolve=ui.button('Continue to definition review').props.onClick;resolve();resolve();ui.render();
  assert.equal(calls.filter(c=>c.path==='semantic/definition/resolve').length,1);
  complete(review);await ui.settle();assert.equal(ui.button('Approve definition and classify supplied items').props.disabled,true);
});

test('cancel is explicit, single use in UI, and cannot classify or apply',async()=>{
  const {calls,ui}=fixture();await show(ui);const cancel=ui.button('Cancel category clarification').props.onClick;cancel();cancel();await ui.settle();
  assert.equal(calls.filter(c=>c.path==='semantic/definition/resolve').length,1);
  assert.equal(calls.find(c=>c.path==='semantic/definition/resolve').body.choice,'cancel');
  assert.ok(ui.text().includes('Nothing was approved or applied'));
  assert.equal(ui.nodes().filter(n=>n.props['aria-label']==='Category definition review').length,0);
  assert.equal(ui.nodes().filter(n=>n.props['aria-label']==='Unapproved primary category').length,0);
});

test('edit clears choice and candidate without calling model or restoring old review',async()=>{
  const {calls,ui}=fixture();await show(ui);choose(ui);const before=calls.length;
  ui.find(n=>n.props.id==='semantic-text').props.onChange({target:{value:'Edited objective'}});ui.render();await ui.settle();
  assert.equal(calls.length,before);assert.equal(ui.nodes().filter(n=>n.props.name==='category-resolution').length,0);
});

for(const phase of ['preview','resolve'])for(const interrupt of ['close','reset','user','edit'])test(`${interrupt} ignores a delayed ${phase} response`,async()=>{
  let complete;const {calls,ui}=fixture(path=>path===`semantic/definition/${phase}`?new Promise(r=>complete=r):undefined);
  await ui.start();ui.button('Propose a definition for review').props.onClick();
  if(phase==='resolve'){await ui.settle();choose(ui);ui.button('Continue to definition review').props.onClick();}
  ui.render();
  if(interrupt==='close')ui.find(n=>n.type==='details').props.onToggle({currentTarget:{open:false}});
  else if(interrupt==='reset')ui.changeProps({resetKey:1});
  else if(interrupt==='user')ui.changeProps({user:2});
  else ui.find(n=>n.props.id==='semantic-text').props.onChange({target:{value:'Newer edit'}});
  ui.render();complete(phase==='preview'?clar:review);await ui.settle();
  if(interrupt==='close'){ui.find(n=>n.type==='details').props.onToggle({currentTarget:{open:true}});ui.render();await ui.settle();}
  assert.equal(ui.nodes().filter(n=>n.props['aria-label']==='Category definition review'||n.props.name==='category-resolution').length,0);
  assert.equal(calls.filter(c=>c.path==='semantic/definition/classify'||c.path==='semantic/apply').length,0);
});

test('failed resolution stays visible and never manufactures a definition review',async()=>{
  const {ui}=fixture(path=>path==='semantic/definition/resolve'?Promise.reject(new Error('Expired clarification')):undefined);
  await show(ui);choose(ui);ui.button('Continue to definition review').props.onClick();await ui.settle();
  assert.ok(ui.text().includes('Expired clarification'));assert.equal(ui.nodes().filter(n=>n.props['aria-label']==='Category definition review').length,0);
});

// Additional authored source-context mechanics, not model semantic evidence.
const fullField='No glue or powered equipment is used.\n"Bread preparation" is quoted, not asserted. 🧭 cafe\u0301 <img src=x onerror="alert(1)"> & '+('distant qualifier ' .repeat(220))+'Only under supervision.';
const contextRow={item_id:1,field:'caption',quote:proposal.evidence[0].quote,supplied_field_text:fullField,truncated:false,quote_present:true};
for(const ordinary of [false,true])test(`full source field remains exact in ${ordinary?'ordinary':'clarification and resolved'} review`,async()=>{
  const withContext=value=>({...structuredClone(value),evidence_context:[structuredClone(contextRow)]});
  const {calls,ui}=fixture(path=>path==='semantic/definition/preview'?withContext(ordinary?review:clar):path==='semantic/definition/resolve'?withContext(review):undefined);
  await show(ui);
  function check(){
    const sourceNode=ui.find(n=>n.props.style?.whiteSpace==='pre-wrap');
    assert.deepEqual(sourceNode.children,[fullField]);
    assert.ok(ui.text().includes(proposal.evidence[0].quote));
    assert.equal(ui.nodes().some(n=>n.props.dangerouslySetInnerHTML),false);
  }
  check();if(!ordinary){choose(ui);ui.button('Continue to definition review').props.onClick();await ui.settle();check();}
  assert.equal(ui.button('Approve definition and classify supplied items').props.disabled,true);
  assert.equal(calls.filter(c=>c.path==='semantic/definition/classify'||c.path==='semantic/apply').length,0);
});

for(const [index,context] of [undefined,[],[{...contextRow,item_id:2}], [{...contextRow,field:'title'}], [{...contextRow,quote:'different quote'}], [{...contextRow,supplied_field_text:null}]].entries())test(`missing or mismatched context is explicit: case ${index}`,async()=>{
  const {ui}=fixture(path=>path==='semantic/definition/preview'?{...structuredClone(clar),evidence_context:context}:undefined);
  await show(ui);assert.ok(ui.text().includes('Full source field unavailable for this citation.'));
  assert.equal(ui.text().includes(fullField),false);
});

test('same field on multiple items is displayed under its matching citation',async()=>{
  const value=structuredClone(clar);
  value.clarification.candidate.evidence.push({...proposal.evidence[0],item_id:2});
  value.evidence_context=[{...contextRow,item_id:2,supplied_field_text:'Second item only'},contextRow];
  const {ui}=fixture(path=>path==='semantic/definition/preview'?value:undefined);await show(ui);
  const sections=ui.nodes().filter(n=>n.props['aria-label']==='Definition cited source context');
  assert.equal(sections.length,2);assert.ok(ui.text(sections[0]).includes(fullField));
  assert.equal(ui.text(sections[0]).includes('Second item only'),false);
  assert.ok(ui.text(sections[1]).includes('Second item only'));assert.equal(ui.text(sections[1]).includes(fullField),false);
});

test('React static serialization escapes full source text instead of creating markup',async()=>{
  const React=await import('react');
  const {renderToStaticMarkup}=await import('react-dom/server');
  const module={exports:{}};
  const renderEvidence=new Function('React','useState','useRef','useEffect','module','exports',compiled+'; return definitionEvidence;')(React,()=>{},()=>{},()=>{},module,module.exports);
  const markup=renderToStaticMarkup(React.createElement('div',null,renderEvidence(proposal.evidence,[contextRow])));
  assert.ok(markup.includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'));
  assert.ok(markup.includes('No glue or powered equipment is used.'));
  assert.equal(markup.includes('<img'),false);
  assert.ok(markup.includes('white-space:pre-wrap'));
});
