import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {describeResearchMode} from '../src/researchLabels.js';

test('authored fixture with diagnostic scorer is labeled directly', () => {
  assert.deepEqual(describeResearchMode({data_mode:'fixture',model_mode:'deterministic diagnostic scorer'}),
    {data:'Authored fixture',scorer:'Diagnostic scorer'});
});
test('trained status does not invent frozen-study provenance', () => {
  assert.deepEqual(describeResearchMode({data_mode:'processed dataset',model_mode:'trained model'}),
    {data:'Dataset mode',scorer:'Trained scorer'});
});
test('missing status stays unverified', () => {
  for (const value of [undefined,null,{},false,'trained model'])
    assert.deepEqual(describeResearchMode(value),{data:'Data not verified',scorer:'Scorer not verified'});
});
test('dataset and scorer identity are independent', () => {
  assert.deepEqual(describeResearchMode({data_mode:'processed dataset',model_mode:'deterministic diagnostic scorer'}),
    {data:'Dataset mode',scorer:'Diagnostic scorer'});
});
test('unrecognized labels are not copied or treated as verified', () => {
  assert.deepEqual(describeResearchMode({data_mode:'PRIVATE_CANARY',model_mode:'PRIVATE_CANARY'}),
    {data:'Data not verified',scorer:'Scorer not verified'});
});
test('fixture data alone does not establish scorer identity', () => {
  assert.deepEqual(describeResearchMode({data_mode:'fixture'}),
    {data:'Authored fixture',scorer:'Scorer not verified'});
});
test('main view uses the mode labels in the prominent heading and condition explanation', () => {
  const source=readFileSync(new URL('../src/main.jsx',import.meta.url),'utf8');
  assert.match(source,/const researchMode = describeResearchMode\(status\)/);
  assert.match(source,/interface conditions\.<br\/>\{researchMode\.scorer\}\.<br\/>\{researchMode\.data\}\./);
  assert.match(source,/replace\(\/\^Baseline scorer\/, researchMode\.scorer\)/);
  assert.match(source,/\{conditionDescription\}/);
  assert.ok(!source.includes('One frozen scorer'));
  assert.ok(!source.includes('Frozen scorer +'));
});
