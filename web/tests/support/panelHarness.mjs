// Offline component harness. It bundles the real panel source and runs its
// handlers and effects against authored API promises. It is not a browser:
// no DOM, no layout and no model. Nested components must be free of hooks.
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';

export const compiled=buildSync({entryPoints:[fileURLToPath(new URL('../../src/SemanticPanel.jsx',import.meta.url))],
  bundle:true,write:false,format:'cjs',external:['react','react-dom'],jsx:'transform',logLevel:'silent'}).outputFiles[0].text;

// Load the bundle with a given React implementation and return its exports.
export function load(React){
  const module={exports:{}};
  new Function('require','module','exports',compiled)(name=>{if(name==='react')return React;throw Error('Unexpected import '+name);},module,module.exports);
  return module.exports;
}

export function harness(api,extraProps={}){
  const slots=[],effects=[];let cursor=0,dirty=false,tree,props={api,user:1,resetKey:0,onFeed:()=>{},...extraProps};
  function useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;
    return [slots[i],value=>{const next=typeof value==='function'?value(slots[i]):value;if(!Object.is(next,slots[i])){slots[i]=next;dirty=true;}}];}
  function useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i];}
  function useEffect(fn,deps){const i=cursor++;if(!(i in slots)||deps.some((x,n)=>!Object.is(x,slots[i][n]))){slots[i]=deps;effects.push(fn);}}
  const React={createElement:(type,props,...children)=>({type,props:props||{},children}),Fragment:'fragment',useState,useRef,useEffect};
  const Component=load(React).default;
  // Nested components are plain functions of their props; call them so that their output can be inspected.
  function expand(node){if(Array.isArray(node))return node.map(expand);if(!node||typeof node!=='object')return node;
    if(typeof node.type==='function')return expand(node.type({...node.props,children:node.children}));
    return {...node,children:node.children.map(expand)};}
  function render(){let n=0;do{dirty=false;cursor=0;tree=expand(Component(props));for(const fn of effects.splice(0))fn();if(++n>30)throw Error('Render loop');}while(dirty);return tree;}
  function nodes(node){if(arguments.length===0)node=tree;if(!node||typeof node!=='object')return [];if(Array.isArray(node))return node.flatMap(nodes);return [node,...node.children.flatMap(nodes)];}
  function text(node){if(arguments.length===0)node=tree;if(node==null||typeof node==='boolean')return '';if(typeof node!=='object')return String(node);if(Array.isArray(node))return node.map(text).join(' ');return node.children.map(text).join(' ');}
  function find(fn){const node=nodes().find(fn);assert.ok(node,'Missing node');return node;}
  function button(label){return find(n=>n.type==='button'&&text(n)===label);}
  function region(label){return find(n=>n.props['aria-label']===label);}
  async function settle(){for(let n=0;n<5;n++){await new Promise(r=>setImmediate(r));render();}}
  async function open(){render();find(n=>n.type==='details').props.onToggle({currentTarget:{open:true}});render();await settle();}
  function choose(id,value){find(n=>n.props.id===id).props.onChange({target:{value}});render();}
  async function start(){await open();choose('semantic-backend','staged');choose('semantic-text','Original objective');}
  function changeProps(next){props={...props,...next};render();}
  return {render,find,button,region,text,nodes,settle,open,choose,start,changeProps};
}
