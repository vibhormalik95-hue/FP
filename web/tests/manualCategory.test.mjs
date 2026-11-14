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


async function manual(ui, categories=['K1','K2']) {
 ui.changeProps({categories}); await ui.start();
 ui.find(n=>n.props.id==='semantic-backend').props.onChange({target:{value:'manual_category'}});ui.render();
}
test('manual choices use loaded IDs and no default',async()=>{
 const {ui,calls}=fixture();await manual(ui);
 const field=ui.find(n=>n.props.id==='semantic-category');assert.equal(field.type,'select');assert.equal(field.props.value,'');
 assert.deepEqual(ui.nodes(field).filter(n=>n.type==='option').map(n=>n.props.value),['','K1','K2']);
 assert.equal(ui.button('Review semantic proposal').props.disabled,true);
 ui.button('Review semantic proposal').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview').length,0);
});
test('chosen category submits and stale choice cannot submit',async()=>{
 const {ui,calls}=fixture(path=>path==='semantic/preview'?{ready:false,status:'clarify',reason:'authored stop'}:undefined);await manual(ui);
 ui.find(n=>n.props.id==='semantic-category').props.onChange({target:{value:'K1'}});ui.render();assert.equal(ui.button('Review semantic proposal').props.disabled,false);
 ui.button('Review semantic proposal').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview')[0].body.category,'K1');
 ui.changeProps({categories:['K2']});assert.equal(ui.find(n=>n.props.id==='semantic-category').props.value,'');assert.equal(ui.button('Review semantic proposal').props.disabled,true);
 ui.button('Review semantic proposal').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview').length,1);
});
test('empty catalogue disables manual control',async()=>{
 const {ui}=fixture();await manual(ui,[]);assert.equal(ui.find(n=>n.props.id==='semantic-category').props.disabled,true);assert.equal(ui.button('Review semantic proposal').props.disabled,true);
});
