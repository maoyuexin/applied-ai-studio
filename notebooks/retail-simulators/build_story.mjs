import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {Play, Pause, ArrowLeft, ArrowRight, RotateCcw, Printer, Check, LockKeyhole, ShoppingBag} from 'lucide-react';
import './engine.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const includeProductPhotos = process.argv.includes('--include-product-photos');
const manifest = JSON.parse(fs.readFileSync(path.join(here, 'product-images.json'), 'utf8'));
const productDefinitions = [
  ['85099B', 'Red bag'], ['85099F', 'Strawberry bag'], ['20725', 'Lunch bag'],
  ['22423', 'Cake stand'], ['47566', 'Bunting'], ['84879', 'Bird ornaments'],
];
const customers = ['Asha', 'Ben', 'Cara', 'Diego', 'Eli'];
const purchases = [[0, 1, 2], [0, 1], [0, 2, 3], [3, 4, 5], [3, 4]];
const matrix = purchases.map(history => productDefinitions.map((_, index) => Number(history.includes(index))));
const counts = productDefinitions.map((_, index) => matrix.reduce((total, row) => total + row[index], 0));
const similarities = productDefinitions.map((_, source) => productDefinitions.map((__, target) => {
  const overlap = matrix.reduce((total, row) => total + row[source] * row[target], 0);
  return overlap / Math.sqrt(counts[source] * counts[target]);
}));
const edges = similarities.map((row, source) => row.map((weight, target) => [target, weight])
  .filter(([target, weight]) => target !== source && weight > 0)
  .sort((left, right) => right[1] - left[1] || left[0] - right[0]).slice(0, 3));
const toy = {
  catalog: productDefinitions.map(([code, name], index) => [code, name, counts[index]]),
  edges, minHistory: 1, slots: 2, fallback: [],
};
const initialHistory = [0, 1];
const changedHistory = [...initialHistory, 3];
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);
close(similarities[0][1], 2 / Math.sqrt(6));
close(similarities[0][3], 1 / 3);
assert.equal(similarities[0][4], 0);
assert.deepEqual(edges[0].map(([target]) => target), [1, 2, 3]);
assert.deepEqual(edges[3].map(([target]) => target), [4, 5, 2]);
assert.ok(!edges[3].some(([target]) => target === 0));
const engine = globalThis.RetailEngine;
const initial = engine.rank(toy, initialHistory);
const changed = engine.rank(toy, changedHistory);
close(initial.scores[2], 2 / Math.sqrt(6) + 0.5);
close(initial.scores[3], 1 / 3);
close(changed.scores[2], 2 / Math.sqrt(6) + 0.5 + 1 / Math.sqrt(6));
assert.deepEqual(initial.result.map(row => row.index), [2, 3]);
assert.deepEqual(changed.result.map(row => row.index), [2, 4]);
assert.deepEqual(engine.recommendationScores(toy, [...initialHistory, 0]), initial.scores);
assert.ok(changed.result.every(row => !changedHistory.includes(row.index)));
assert.ok(changed.result.every(row => row.source === 'personalized'));
for (const history of [initialHistory, changedHistory]) {
  for (const {index, score} of engine.rank(toy, history).result) {
    close(engine.contributions(toy, history, index).reduce((total, link) => total + link.weight, 0), score);
  }
}
console.log('PASS teaching example: binary matrix, cosine, top-3 pruning, score sums, purchase masking, repeat invariance, changed ranking');

if (!process.argv.includes('--check')) {
  const simulator = fs.readFileSync(path.resolve(here, '../product-recommendations/backup/02_recommendation_simulator.html'), 'utf8');
  const real = JSON.parse(simulator.match(/<script id="model-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const photos = productDefinitions.map(([code, name]) => {
    const record = manifest.products[code];
    assert.equal(record.kind, 'matched');
    return {code, name, fullName: record.name, credit: record.credit, sourcePage: record.sourcePage,
      src: includeProductPhotos ? `data:image/webp;base64,${fs.readFileSync(path.join(here, record.file)).toString('base64')}` : null};
  });
  const data = {customers, purchases, matrix, counts, similarities, toy, initialHistory, changedHistory, photos,
    real: {products: real.catalog.length, neighbors: Math.max(...real.edges.map(row => row.length)),
      minHistory: real.minHistory, slots: real.slots, cut: real.cut}, imageRights: manifest.notice};
  const iconComponents = {Play, Pause, ArrowLeft, ArrowRight, RotateCcw, Printer, Check, LockKeyhole, ShoppingBag};
  const icons = Object.fromEntries(Object.entries(iconComponents).map(([name, component]) => [name,
    renderToStaticMarkup(React.createElement(component, {size: 20, 'aria-hidden': true}))]));
  const replacements = {
    '__STORY_DATA__': JSON.stringify(data).replaceAll('<', '\\u003c'),
    '__ICONS__': JSON.stringify(icons).replaceAll('<', '\\u003c'),
    '__ENGINE__': fs.readFileSync(path.join(here, 'engine.js'), 'utf8'),
  };
  let html = fs.readFileSync(path.join(here, 'story.html'), 'utf8');
  for (const [marker, value] of Object.entries(replacements)) html = html.replace(marker, () => value);
  assert.ok(!/__STORY_DATA__|__ICONS__|__ENGINE__/.test(html));
  const destination = path.resolve(here, '../product-recommendations/backup/03_recommendation_story.html');
  fs.writeFileSync(destination, html);
  for (const folder of ['../product-recommendations', '../product-recommendations/backup']) {
    fs.writeFileSync(path.resolve(here, folder, 'M6_Explainer_How_Recommendations_Work.html'), html);
  }
  console.log(`Built ${destination} (${Buffer.byteLength(html).toLocaleString()} bytes)`);
}