// Offline component contract harness. Runs real JSX handlers and effects against
// authored API promises; no DOM/browser or live-model validation is claimed.
import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './support/panelHarness.mjs';
const saved={groups:[],feed:{baseline_items:[1,2]},local_models_allowed:false,external_adapter_available:false,category_adapter_available:true,can_undo:false};

function fixture(override=()=>undefined){const calls=[];const api=async(path,body)=>{calls.push({path,body});const supplied=override(path,body);if(supplied!==undefined)return supplied;
  if(path.startsWith('semantic/groups'))return structuredClone(saved);
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
 assert.equal(ui.button('Show the proposed change').props.disabled,true);
 ui.button('Show the proposed change').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview').length,0);
});
test('chosen category submits and stale choice cannot submit',async()=>{
 const {ui,calls}=fixture(path=>path==='semantic/preview'?{ready:false,status:'clarify',reason:'authored stop'}:undefined);await manual(ui);
 ui.find(n=>n.props.id==='semantic-category').props.onChange({target:{value:'K1'}});ui.render();assert.equal(ui.button('Show the proposed change').props.disabled,false);
 ui.button('Show the proposed change').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview')[0].body.category,'K1');
 ui.changeProps({categories:['K2']});assert.equal(ui.find(n=>n.props.id==='semantic-category').props.value,'');assert.equal(ui.button('Show the proposed change').props.disabled,true);
 ui.button('Show the proposed change').props.onClick();await ui.settle();assert.equal(calls.filter(c=>c.path==='semantic/preview').length,1);
});
test('empty catalogue disables manual control',async()=>{
 const {ui}=fixture();await manual(ui,[]);assert.equal(ui.find(n=>n.props.id==='semantic-category').props.disabled,true);assert.equal(ui.button('Show the proposed change').props.disabled,true);
});
