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
test('main view shows current scorer and data disclosures and passes provider identity to review', () => {
  const source=readFileSync(new URL('../src/main.jsx',import.meta.url),'utf8');
  assert.match(source,/aria-label="Research environment"/);
  assert.match(source,/\{scorerWords\}/);
  assert.ok(source.includes('deterministic diagnostic scorer (a fixed formula, not the trained recommender)'));
  assert.ok(source.includes('The items of this scenario are invented for the demonstration.'));
  assert.ok(source.includes('The items are a built-in fixture, not the research dataset.'));
  assert.match(source,/provider=\{status\?\.provider\}/);
  assert.match(source,/dataNote=\{dataNote\}/);
  assert.ok(!source.includes('One frozen scorer'));
  assert.ok(!source.includes('Frozen scorer +'));
});

test('main view never infers dataset or scorer identity from an unknown mode', () => {
  const source=readFileSync(new URL('../src/main.jsx',import.meta.url),'utf8');
  const statements=['researchMode','dataKind','diagnostic','scorerWords'].map(name => {
    const line=source.split('\n').find(line=>line.trim().startsWith(`const ${name} =`));
    assert.ok(line,`missing ${name}`);return line;
  }).join('\n');
  const labels=new Function('status','describeResearchMode', statements+'\nreturn {dataKind,diagnostic,scorerWords};');
  for (const status of [null,{}, {data_mode:'unknown',model_mode:'unknown'}]) {
    assert.deepEqual(labels(status,describeResearchMode),{dataKind:'unknown',diagnostic:false,scorerWords:'Scorer not verified'});
  }
  assert.equal(labels({data_mode:'fixture',source:'deterministic fixture',model_mode:'trained model'},describeResearchMode).dataKind,'fixture');
  assert.equal(labels({data_mode:'processed dataset',model_mode:'trained model'},describeResearchMode).scorerWords,'trained recommender');
  assert.match(source,/dataKind === 'unknown' \? 'The data source is not verified/);
  assert.ok(source.includes('DATA NOT VERIFIED'));
});
