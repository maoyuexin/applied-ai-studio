import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath, pathToFileURL} from 'node:url';
import './engine.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const engine = globalThis.RetailEngine;
const output = process.env.SIMULATOR_TEST_OUTPUT || '/tmp/m6-retail-simulator-tests';
fs.mkdirSync(output, {recursive:true});
const files = {
  recommendations:path.resolve(here,'../product-recommendations/backup/02_recommendation_simulator.html'),
  forecast:path.resolve(here,'../demand-forecasting/backup/02_forecast_simulator.html'),
};
const payloads = {};
for (const [kind, filename] of Object.entries(files)) {
  const html = fs.readFileSync(filename,'utf8');
  payloads[kind] = JSON.parse(html.match(/<script id="model-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  assert.ok(!/__(?:STYLE|ENGINE|COMMON|PLOTLY|DATA|ICONS)__/.test(html));
  assert.ok(!/<(?:script|img|link)[^>]*(?:src|href)=["']https?:\/\//.test(html));
  for (const script of html.matchAll(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
    if ((script[1] || '').includes('application/json')) continue;
    new vm.Script(script[2]);
  }
}
const rec = payloads.recommendations, fc = payloads.forecast;
assert.equal(rec.catalog.length, 4443);
const withPhotos = Object.keys(rec.productImages).length > 0;
assert.equal(Object.keys(rec.productImages).length,withPhotos ? 25 : 0);
assert.equal(Object.keys(fc.productImages).length,withPhotos ? 9 : 0);
assert.ok(!('illustrations' in rec)&&!('illustrations' in fc));
const manifest=JSON.parse(fs.readFileSync(path.join(here,'product-images.json'),'utf8'));
for(const data of [rec,fc]){
  for(const [code,photo] of Object.entries(data.productImages)){
    assert.equal(photo.src,'data:image/webp;base64,'+fs.readFileSync(path.join(here,manifest.products[code].file)).toString('base64'));
    assert.equal(photo.sourcePage,manifest.products[code].sourcePage);
    assert.ok(['matched','reference'].includes(photo.kind));
    assert.ok(photo.name&&photo.match&&photo.credit);
  }
}
assert.equal(new Set(Object.values(rec.productImages).map(photo=>photo.src)).size,withPhotos ? 25 : 0);
if (withPhotos) {
  assert.equal(rec.productImages['22386'].kind,'reference');
  assert.equal(fc.productImages['85099B'].src,rec.productImages['85099B'].src);
}
for (const fixture of rec.fixtures) {
  const scores = engine.recommendationScores(rec, fixture.history);
  scores.forEach((score,index) => assert.ok(Math.abs(score - fixture.scores[index]) < 1e-6));
  const ranked = engine.rank(rec,fixture.history);
  assert.equal(ranked.result.length,10);
  assert.ok(ranked.result.every(row => !fixture.history.includes(row.index)));
  for (const row of ranked.result.filter(row => row.source === 'personalized')) {
    const sum = engine.contributions(rec,fixture.history,row.index).reduce((total,link) => total+link.weight,0);
    assert.ok(Math.abs(sum-row.score)<1e-9);
  }
}
assert.deepEqual(engine.recommendationScores(rec,[...rec.starter,rec.starter[0]]),engine.recommendationScores(rec,rec.starter));
assert.equal(engine.rank(rec,rec.starter.slice(0,4)).personalized,false);
assert.equal(engine.rank(rec,rec.starter).personalized,true);
const blocked = engine.rank(rec,rec.starter).result[0].index;
assert.ok(engine.rank(rec,rec.starter,[blocked]).result.every(row=>row.index!==blocked));
for (const fixture of fc.fixtures) assert.ok(Math.abs(engine.predict(fc,fixture.features)-fixture.prediction)<1e-8);
for (const fixture of fc.fixtures.slice(0,8)) {
  const why = engine.explain(fc,fixture.features);
  assert.ok(Math.abs(why.reference+why.effects.reduce((sum,value)=>sum+value,0)-why.prediction)<1e-8);
}
console.log('PASS model parity: 4 complete recommendation score vectors, 88 forecasts, repeated history, exclusions, Shapley additivity');

// Classroom customer roster: deterministic selection, real histories, held-out truth.
assert.equal(rec.customers.length,13);
assert.ok(rec.customers.some(record=>record.id===rec.defaultCustomer));
assert.equal(rec.defaultCustomer,12349);
assert.deepEqual(rec.customers.map(record=>record.history.length),
  [...rec.customers.map(record=>record.history.length)].sort((left,right)=>left-right));
for (const record of rec.customers) {
  assert.ok(record.history.length>=rec.minHistory);
  assert.deepEqual(record.history,[...new Set(record.history)].sort((left,right)=>left-right));
  assert.ok(record.truth.length>0);
  assert.ok(record.history.every(index=>index>=0&&index<rec.catalog.length));
  assert.ok(record.truth.every(index=>index>=0&&index<rec.catalog.length));
  assert.ok(record.truth.every(index=>!record.history.includes(index)));
  const ranked=engine.rank(rec,record.history);
  assert.equal(ranked.result.length,rec.slots);
  assert.ok(ranked.result.every(row=>!record.history.includes(row.index)));
}
assert.deepEqual(rec.customers.find(record=>record.id===12349).history,rec.customer);
const hitCount=rec.customers.filter(record=>{
  const truth=new Set(record.truth);
  return engine.rank(rec,record.history).result.some(row=>truth.has(row.index));
}).length;
assert.ok(hitCount>=4&&hitCount<=8,`roster hit rate ${hitCount}/13 should resemble the ${rec.hitRate} population rate`);
console.log(`PASS customer roster: 13 real customers, ${rec.customers[0].history.length}-${rec.customers.at(-1).history.length} products, disjoint held-out truth, ${hitCount}/13 top-ten hits against a ${(rec.hitRate*100).toFixed(1)}% population rate`);

// Replay parity: every held-out week forecast from recorded history only, no compounding.
const TEST_WEEKS = fc.weeks.length - fc.firstTest;
assert.equal(TEST_WEEKS,26);
const replay = fc.products.map(product => {
  const rows=[];
  for (let week=fc.firstTest; week<fc.weeks.length; week++) {
    const features=engine.featureRow(product.units,week,fc.weekNumbers[week]);
    rows.push({date:fc.weeks[week],forecast:engine.predict(fc,features),baseline:features[6],actual:product.units[week]});
  }
  const mean=key=>rows.reduce((sum,row)=>sum+Math.abs(row[key]-row.actual),0)/rows.length;
  return {code:product.code,rows,model:mean('forecast'),baseline:mean('baseline')};
});
for (const product of replay) {
  assert.equal(product.rows.length,26);
  assert.ok(product.rows.every(row=>Number.isFinite(row.forecast)&&row.forecast>=0));
}
const retrospot = replay.find(product=>product.code==='85099B');
assert.ok(Math.abs(retrospot.rows[24].forecast-824.1539579130387)<1e-9);
assert.equal(retrospot.rows[24].date,'2011-11-21');
assert.equal(retrospot.rows[24].actual,753);
const winners = replay.filter(product=>product.model<product.baseline).length;
assert.equal(winners,5,'the model should beat the 8-week average on 5 of these 10 products');
console.log('PASS replay parity: 260 held-out forecasts, frozen 2011-11-21 value, 5 of 10 products where the model beats the baseline');

const playwright = process.env.PLAYWRIGHT_MODULE;
if (!playwright) {
  console.log('Browser tests not run: set PLAYWRIGHT_MODULE to a Playwright module path.');
  process.exit(0);
}
const playwrightModule = await import(playwright);
const chromium = playwrightModule.chromium || playwrightModule.default.chromium;
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'});
const errors = [], requests = [];
const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
await context.route(/^https?:\/\//,route => {requests.push(route.request().url());return route.abort();});
const page = await context.newPage();
page.on('pageerror',error=>errors.push(error.message));
page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
const simulatorState = () => page.evaluate(()=>retailSimulator.getState());

async function assertVisualState(kind, width) {
  await page.setViewportSize({width,height:1000});
  await page.waitForFunction(()=>[...document.querySelectorAll('.js-plotly-plot')].every(element=>Math.abs(element._fullLayout.width-element.clientWidth)<2));
  await page.waitForFunction(()=>[...document.querySelectorAll('.sankey-node rect')].every(element=>{
    const node=element.getBoundingClientRect(),chart=element.closest('.js-plotly-plot').getBoundingClientRect();
    return node.left>=chart.left-1&&node.right<=chart.right+1;
  }),null,{timeout:5000,polling:100});
  const report = await page.evaluate(()=>({
    overflow:document.documentElement.scrollWidth-innerWidth,
    background:getComputedStyle(document.body).backgroundColor,
    text:getComputedStyle(document.body).color,
    images:[...document.images].every(image=>image.complete&&image.naturalWidth>0),
    smallButtons:[...document.querySelectorAll('button')].filter(element=>element.getBoundingClientRect().height>0&&element.getBoundingClientRect().height<44).length,
    charts:[...document.querySelectorAll('.js-plotly-plot')].map(element=>({width:element._fullLayout.width,color:element._fullLayout.font.color,marks:element.querySelectorAll('.sankey-node,.point,.js-line,.bars path').length})),
  }));
  assert.ok(report.overflow<=1,JSON.stringify(report));
  assert.equal(report.background,'rgb(17, 19, 24)');
  assert.equal(report.text,'rgb(245, 243, 240)');
  assert.ok(report.images);
  assert.equal(report.smallButtons,0);
  assert.ok(report.charts.length>0);
  assert.ok(report.charts.every(chart=>chart.color==='#f5f3f0'&&chart.marks>0),JSON.stringify(report.charts));
  await page.screenshot({path:path.join(output,`${kind}-${width}.png`),fullPage:true});
  console.log(`PASS ${kind} / ${width}px: dark tokens, images, chart marks, 44px controls, no overflow`);
}

try {
  // ---------------------------------------------------------------- Next Best Product
  await page.goto(pathToFileURL(files.recommendations).href);
  await page.waitForFunction(()=>window.retailSimulator && document.querySelectorAll('.sankey-node').length>0);

  // Step 1: the page opens on a real customer with their real history already loaded.
  const opening = await simulatorState();
  assert.equal(opening.customer,rec.defaultCustomer);
  assert.deepEqual(opening.history,rec.customers.find(record=>record.id===rec.defaultCustomer).history);
  assert.equal(await page.locator('#customer option').count(),13);
  assert.equal(await page.locator('#history-count').innerText(),String(opening.history.length));
  assert.equal(await page.locator('#ranking .rank-item').count(),10);
  assert.equal(await page.locator('#engine-state').innerText(),'Personalized');
  assert.ok(opening.anchor!==null && opening.history.includes(opening.anchor));
  assert.equal(await page.locator('.basis-item.selected').count(),1);
  await assertVisualState('recommendations',1440);

  // Step 2: switching customer loads that customer's real history and purchase list.
  const small = rec.customers[0];
  await page.locator('#customer').selectOption(String(small.id));
  assert.deepEqual((await simulatorState()).history,small.history);
  assert.equal(await page.locator('#history-count').innerText(),String(small.history.length));
  assert.equal(await page.locator('#purchase option').count(),small.history.length);
  assert.equal(await page.locator('#ranking .rank-item').count(),10);

  // Step 3: picking a different purchase changes the anchor, not the personalized ranking.
  await page.locator('#customer').selectOption(String(rec.defaultCustomer));
  const beforeAnchor = await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>row.index));
  const otherPurchase = await page.locator('#purchase option').nth(3).getAttribute('value');
  await page.locator('#purchase').selectOption(otherPurchase);
  assert.equal((await simulatorState()).anchor,Number(otherPurchase));
  assert.deepEqual(await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>row.index)),beforeAnchor,
    'the selected purchase must not change a whole-history ranking');
  assert.match(await page.locator('#ranking-footnote').innerText(),/sum of similarity links/);

  // Step 4: Recommend top 10 reproduces the engine exactly, and every score is its contribution sum.
  await page.locator('#recommend').click();
  const ranked = await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>({index:row.index,score:row.score,source:row.source})));
  assert.equal(ranked.length,10);
  const expected = engine.rank(rec,rec.customers.find(record=>record.id===rec.defaultCustomer).history);
  assert.deepEqual(ranked.map(row=>row.index),expected.result.map(row=>row.index));
  for (const row of ranked.filter(row=>row.source==='personalized')) {
    const sum = engine.contributions(rec,opening.history,row.index).reduce((total,link)=>total+link.weight,0);
    assert.ok(Math.abs(sum-row.score)<1e-9);
  }

  // Step 5: the held-out reveal marks the real later purchases, and 12349 hits in slot 4.
  await page.locator('#reveal-truth').check();
  const truth = new Set(rec.customers.find(record=>record.id===rec.defaultCustomer).truth);
  const hitSlots = ranked.map((row,index)=>truth.has(row.index)?index+1:null).filter(Boolean);
  assert.deepEqual(hitSlots,[4]);
  assert.equal(await page.locator('#ranking .rank-item.hit').count(),1);
  assert.match(await page.locator('#truth-note').innerText(),/slot 4/);
  await page.locator('#reveal-truth').uncheck();

  // Step 6: "only the purchase above" is the anchor's nearest neighbours, sorted, never a personal claim.
  await page.locator('#mode button[data-mode="neighbor"]').click();
  const neighbourState = await simulatorState();
  const neighbourRanking = await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>({index:row.index,score:row.score,source:row.source})));
  const excluded = new Set(neighbourState.history);
  const expectedNeighbours = rec.edges[neighbourState.anchor].filter(edge=>!excluded.has(edge[0]))
    .sort((left,right)=>right[1]-left[1]||left[0]-right[0]).slice(0,10);
  assert.deepEqual(neighbourRanking.map(row=>row.index),expectedNeighbours.map(edge=>edge[0]));
  assert.ok(neighbourRanking.every((row,index)=>index===0||row.score<=neighbourRanking[index-1].score));
  assert.ok(neighbourRanking.every(row=>row.source==='neighbor'));
  assert.equal(await page.locator('#engine-state').innerText(),'Bought together');
  assert.match(await page.locator('#ranking-footnote').innerText(),/not a personalized recommendation/);
  assert.match(await page.locator('#contribution-heading').innerText(),/Similarity to the selected purchase/);

  // Step 7: popularity baseline ignores the customer entirely.
  await page.locator('#mode button[data-mode="popularity"]').click();
  const expectedPopular = rec.catalog.map((_,index)=>index).filter(index=>!opening.history.includes(index))
    .sort((left,right)=>rec.catalog[right][2]-rec.catalog[left][2]||left-right).slice(0,10);
  assert.deepEqual(await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>row.index)),expectedPopular);
  assert.equal(await page.locator('#ranking-title').innerText(),'Popular with everyone');
  assert.match(await page.locator('#contribution-table').innerText(),/No personal history/);
  assert.match(await page.locator('#basis-note').innerText(),/None of these purchases are used/);
  await page.locator('#mode button[data-mode="history"]').click();

  // Step 8: merchandiser exclusion drops a product; undo puts the ranking back.
  const dropped = await page.evaluate(()=>retailSimulator.getState().selected);
  await page.locator('#exclude').click();
  assert.ok(!await page.evaluate(index=>retailSimulator.getState().ranking.some(row=>row.index===index),dropped));
  await page.locator('#undo').click();
  assert.deepEqual(await page.evaluate(()=>retailSimulator.getState().ranking.map(row=>row.index)),expected.result.map(row=>row.index));

  // Step 9: the cold-start policy still bites when history is cut below five products.
  await page.locator('#customer').selectOption(String(small.id));
  await page.locator('#workbench').evaluate(element=>{element.open=true;});
  await page.locator('#history-title').click();
  for (const index of small.history.slice(0,small.history.length-4)) {
    await page.locator(`[data-forget="${index}"]`).click();
  }
  assert.equal(await page.locator('#engine-state').innerText(),'Cold start');
  assert.ok(await page.evaluate(()=>retailSimulator.getState().ranking.every(row=>row.source==='fallback'&&row.score===null)));
  assert.match(await page.locator('#ranking-footnote').innerText(),/fewer than five products/);

  // Step 10: adding a product back through the basket restores personalization and changes the ranking.
  await page.locator('#search').fill(rec.catalog[small.history[0]][0]);
  await page.locator(`#catalog [data-add="${small.history[0]}"]`).click();
  assert.equal(await page.locator('#basket-count').innerText(),'1');
  await page.locator('#purchase-button').click();
  assert.equal(await page.locator('#engine-state').innerText(),'Personalized');
  await page.locator('#search').fill('');
  await page.locator('#customer').selectOption(String(rec.defaultCustomer));

  // Step 11: the exported session records the customer, the basis and the held-out outcome.
  const downloaded = page.waitForEvent('download');
  await page.locator('#export').click();
  const session = JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
  assert.equal(session.simulation,true);
  assert.equal(session.customer,rec.defaultCustomer);
  assert.equal(session.rankedBy,'history');
  assert.equal(session.ranking.length,10);
  assert.equal(session.ranking.filter(row=>row.boughtAfterCut).length,1);

  for (const width of [390,768,1440]) await assertVisualState('recommendations',width);
  console.log('PASS recommendations: 13-customer roster, purchase selection, exact engine parity, held-out reveal, neighbour and popularity modes, exclusions, cold start, export');

  // ---------------------------------------------------------------- Demand Forecasting replay
  await page.goto(pathToFileURL(files.forecast).href);
  await page.waitForFunction(()=>window.retailSimulator);

  // Step 1: the model is already loaded and the replay is parked before week one.
  if (withPhotos) assert.equal(await page.locator('#product-media img').getAttribute('data-photo-code'),'84029E');
  else assert.match(await page.locator('#product-media').innerText(),/Photo unavailable/);
  assert.equal(await page.locator('#week-counter').innerText(),`0 of ${TEST_WEEKS}`);
  assert.equal(await page.locator('#forecast-value').innerText(),'--');
  assert.equal(await page.locator('#actual-value').innerText(),'--');
  assert.equal(await page.locator('#phase-chip').innerText(),'Ready');
  assert.equal(await page.locator('#export').isDisabled(),true);

  // Step 2: one Step forecasts the week; the week itself is still hidden.
  await page.locator('#step').click();
  const hottie = replay.find(product=>product.code==='84029E');
  assert.equal(await page.locator('#week-counter').innerText(),`1 of ${TEST_WEEKS}`);
  assert.equal(await page.locator('#phase-chip').innerText(),'Forecast made / week not revealed');
  assert.equal(await page.locator('#actual-value').innerText(),'--');
  assert.ok(Math.abs(await page.evaluate(()=>retailSimulator.getState().forecast)-hottie.rows[0].forecast)<1e-9);
  await page.waitForFunction(()=>document.querySelectorAll('.waterfalllayer .point').length===6);

  // Step 3: the next Step reveals what sold and starts the running error.
  await page.locator('#step').click();
  assert.equal(await page.locator('#phase-chip').innerText(),'Week revealed');
  assert.equal(await page.locator('#actual-value').innerText(),hottie.rows[0].actual.toLocaleString('en-US',{maximumFractionDigits:0}));
  assert.equal(await page.locator('#week-counter').innerText(),`1 of ${TEST_WEEKS}`);
  const firstError = await page.evaluate(()=>retailSimulator.runningError());
  assert.equal(firstError.weeks,1);
  assert.ok(Math.abs(firstError.model-Math.abs(hottie.rows[0].forecast-hottie.rows[0].actual))<1e-9);
  assert.equal(await page.locator('#scoreboard tr').count(),1);
  assert.equal(await page.locator('#export').isDisabled(),false);

  // Step 4: Play runs the transport and Pause stops it where it is.
  await page.locator('#speed').selectOption('350');
  await page.locator('#play').click();
  assert.equal(await page.evaluate(()=>retailSimulator.getState().playing),true);
  await page.waitForFunction(()=>retailSimulator.getState().step>=4,null,{timeout:8000});
  await page.locator('#play').click();
  const paused = await page.evaluate(()=>retailSimulator.getState().step);
  assert.equal(await page.evaluate(()=>retailSimulator.getState().playing),false);
  await page.waitForTimeout(700);
  assert.equal(await page.evaluate(()=>retailSimulator.getState().step),paused);
  assert.match(await page.locator('#play').innerText(),/Play/);

  // Step 5: every scored week matches the offline replay; no prediction is ever fed back in.
  await page.evaluate(weeks=>retailSimulator.goTo(weeks),TEST_WEEKS);
  assert.equal(await page.locator('#week-counter').innerText(),`${TEST_WEEKS} of ${TEST_WEEKS}`);
  assert.equal(await page.locator('#scoreboard tr').count(),TEST_WEEKS);
  const finished = await page.evaluate(()=>retailSimulator.runningError());
  assert.equal(finished.weeks,TEST_WEEKS);
  assert.ok(Math.abs(finished.model-hottie.model)<1e-9);
  assert.ok(Math.abs(finished.baseline-hottie.baseline)<1e-9);
  assert.match(await page.locator('#scoreboard-note').innerText(),/The model is closer on average/);

  // Step 6: what-if edits recompute the forecast and never touch what actually sold.
  const soldThisWeek = await page.locator('#actual-value').innerText();
  const recorded = await page.evaluate(()=>retailSimulator.getState().forecast);
  await page.locator('#whatif').evaluate(element=>{element.open=true;});
  await page.locator('#increase').click();
  assert.notEqual(await page.evaluate(()=>retailSimulator.getState().forecast),recorded);
  assert.equal(await page.locator('#actual-value').innerText(),soldThisWeek);
  assert.equal(await page.locator('#phase-chip').innerText(),'What-if inputs');
  assert.match(await page.locator('#additive-check').innerText(),/passed/);
  await page.locator('#restore').click();
  assert.equal(await page.evaluate(()=>retailSimulator.getState().forecast),recorded);

  // Step 7: an impossible input holds the forecast rather than guessing.
  await page.locator('[data-week="7"]').fill('-1');
  await page.locator('[data-week="7"]').press('Tab');
  assert.equal(await page.locator('#forecast-value').innerText(),'Unavailable');
  assert.equal(await page.evaluate(()=>retailSimulator.getState().forecast),null);
  await page.locator('#restore').click();
  assert.equal(await page.locator('#forecast-value').innerText().then(text=>text!=='Unavailable'),true);

  // Step 8: the frozen classroom value survives on 85099B, week 2011-11-21.
  await page.locator('#product').selectOption(String(fc.products.findIndex(product=>product.code==='85099B')));
  assert.equal(await page.locator('#week-counter').innerText(),`0 of ${TEST_WEEKS}`);
  await page.evaluate(()=>retailSimulator.goTo(25));
  assert.equal(await page.locator('#week-date').innerText(),'2011-11-21');
  assert.ok(Math.abs(await page.evaluate(()=>retailSimulator.getState().forecast)-824.1539579130387)<1e-9);
  assert.equal(await page.locator('#actual-value').innerText(),'753');
  assert.match(await page.locator('#scoreboard-note').innerText(),/8-week average is closer/);

  // Step 9: a product with no photograph still forecasts, and says so plainly.
  await page.locator('#product').selectOption('4');
  assert.equal(await page.locator('#product-media img').count(),0);
  assert.match(await page.locator('#product-media').innerText(),/Photo unavailable/);
  await page.locator('#step').click();
  await page.locator('#step').click();
  assert.ok(await page.evaluate(()=>Number.isFinite(retailSimulator.getState().forecast)));

  // Step 10: the export carries every scored week, not just the one on screen.
  await page.locator('#product').selectOption(String(fc.products.findIndex(product=>product.code==='84029E')));
  await page.evaluate(weeks=>retailSimulator.goTo(weeks),TEST_WEEKS);
  const forecastDownload = page.waitForEvent('download');
  await page.locator('#export').click();
  const scenario = JSON.parse(fs.readFileSync(await (await forecastDownload).path(),'utf8'));
  assert.equal(scenario.simulation,true);
  assert.equal(scenario.product,'84029E');
  assert.equal(scenario.weeks.length,TEST_WEEKS);
  assert.equal(scenario.currentWeekHypothetical,null);
  assert.ok(Math.abs(scenario.averageMiss.model-hottie.model)<1e-9);

  for (const width of [390,768,1440]) await assertVisualState('forecast',width);
  console.log('PASS forecast: parked start, forecast-then-reveal beats, play/pause transport, 26-week parity, running error, what-if hold, frozen value, photoless product, replay export');

  assert.deepEqual(errors,[]);
  assert.deepEqual(requests,[]);
  console.log('PASS: zero page/console errors, zero attempted HTTP requests. Screenshots:',output);
} finally {
  await browser.close();
}
