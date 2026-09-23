import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath, pathToFileURL} from 'node:url';
import './engine.js';

const here=path.dirname(fileURLToPath(import.meta.url));
const filename=path.resolve(here,'../product-recommendations/backup/03_recommendation_story.html');
const html=fs.readFileSync(filename,'utf8');
const data=JSON.parse(html.match(/<script id="story-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const simulator=fs.readFileSync(path.resolve(here,'../product-recommendations/backup/02_recommendation_simulator.html'),'utf8');
const real=JSON.parse(simulator.match(/<script id="model-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
assert.ok(!/__STORY_DATA__|__ICONS__|__ENGINE__/.test(html));
assert.ok(!/<(?:script|img|link)[^>]*(?:src|href)=["']https?:\/\//.test(html));
for(const script of html.matchAll(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
  if(!(script[1]||'').includes('application/json'))new vm.Script(script[2]);
}
assert.deepEqual(data.counts,[3,2,2,3,2,1]);
assert.equal(data.matrix.length,5);
assert.ok(data.matrix.every(row=>row.length===6&&row.every(value=>value===0||value===1)));
assert.deepEqual(data.real,{products:real.catalog.length,neighbors:15,minHistory:real.minHistory,slots:real.slots,cut:real.cut});
for(const photo of data.photos) {
  if (photo.src) {
    assert.equal(photo.src,real.productImages[photo.code].src);
    assert.equal(photo.sourcePage,real.productImages[photo.code].sourcePage);
  } else {
    assert.equal(photo.src,null);
    assert.ok(!real.productImages[photo.code]);
  }
}
const engine=globalThis.RetailEngine;
const before=engine.rank(data.toy,data.initialHistory);
const after=engine.rank(data.toy,data.changedHistory);
assert.deepEqual(before.result.map(row=>row.index),[2,3]);
assert.deepEqual(after.result.map(row=>row.index),[2,4]);
assert.ok(Math.abs(before.scores[2]-(2/Math.sqrt(6)+0.5))<1e-12);
assert.ok(Math.abs(after.scores[2]-(3/Math.sqrt(6)+0.5))<1e-12);
assert.deepEqual(engine.recommendationScores(data.toy,[0,1,0,0]),before.scores);
assert.ok(!data.toy.edges[3].some(([target])=>target===0));
console.log('PASS: exact teaching scores, binary matrix, masking, repeat invariance, directional pruning, photo bytes, real-model settings, embedded syntax');

if(!process.env.PLAYWRIGHT_MODULE) {
  console.log('Browser checks not run: set PLAYWRIGHT_MODULE.');
  process.exit(0);
}
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE);
const output=process.env.STORY_TEST_OUTPUT||'/tmp/m6-recommendation-story-tests';
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'});
const errors=[],requests=[];
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await page.route(/^https?:\/\//,route=>{requests.push(route.request().url());return route.abort();});
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  await page.clock.install({time:0});
  await page.clock.pauseAt(1000);
  await page.goto(pathToFileURL(filename).href);
  assert.equal(await page.locator('.scene:visible').count(),1);
  assert.equal(await page.locator('.matrix td').count(),30);
  assert.equal(await page.locator('.matrix td.yes').count(),13);
  assert.equal(await page.locator('.pair-table .overlap').count(),2);
  assert.deepEqual(await page.locator('#score-history>.item').evaluateAll(items=>items.map(item=>getComputedStyle(item).borderBottomColor)),['rgb(232, 145, 60)','rgb(126, 174, 184)']);
  await page.locator('[data-step="3"]').click();
  assert.equal(await page.locator('.neighbor-row[data-kept="true"]').count(),3);
  await page.locator('#source').selectOption('3');
  assert.deepEqual(await page.locator('.neighbor-row[data-kept="true"]').evaluateAll(rows=>rows.map(row=>Number(row.dataset.target))),[4,5,2]);
  await page.locator('#source').selectOption('0');
  await page.locator('[data-step="5"]').click();
  assert.deepEqual(await page.locator('#ranking-after [data-product]').evaluateAll(rows=>rows.map(row=>Number(row.dataset.product))),[2,3]);
  const frozenEdges=await page.evaluate(()=>JSON.stringify(retailStory.data.toy.edges));
  await page.locator('#purchase-cake').check();
  assert.deepEqual(await page.locator('#ranking-after [data-product]').evaluateAll(rows=>rows.map(row=>Number(row.dataset.product))),[2,4]);
  assert.match(await page.locator('#ranking-after').innerText(),/1\.725/);
  assert.equal(await page.evaluate(()=>JSON.stringify(retailStory.data.toy.edges)),frozenEdges);
  await page.locator('#purchase-cake').uncheck();
  assert.deepEqual(await page.locator('#ranking-after [data-product]').evaluateAll(rows=>rows.map(row=>Number(row.dataset.product))),[2,3]);
  for(const width of [1440,768,390,375]) {
    await page.setViewportSize({width,height:1000});
    for(let step=0;step<7;step++) {
      await page.locator(`[data-step="${step}"]`).click();
      const report=await page.evaluate(()=>({
        overflow:document.documentElement.scrollWidth-innerWidth,
        images:[...document.images].every(image=>image.complete&&image.naturalWidth>0),
        background:getComputedStyle(document.body).backgroundColor,
        smallButtons:[...document.querySelectorAll('button')].filter(button=>button.getClientRects().length&&
          (button.getBoundingClientRect().height<44||button.getBoundingClientRect().width<44)).map(button=>button.id||button.textContent),
        clipped:[...document.querySelectorAll('.scene.active h2,.scene.active p,.scene.active th,.scene.active td')].filter(element=>element.scrollWidth>element.clientWidth+1).map(element=>element.textContent),
      }));
      assert.ok(report.overflow<=1,`${width}/step${step+1}: ${JSON.stringify(report)}`);
      assert.ok(report.images);
      assert.equal(report.background,'rgb(17, 19, 24)');
      assert.deepEqual(report.smallButtons,[],`${width}/step${step+1}`);
      assert.deepEqual(report.clipped,[],`${width}/step${step+1}`);
      if(width===1440||width===390)await page.screenshot({path:path.join(output,`step-${step+1}-${width}.png`),fullPage:true});
    }
    console.log(`PASS: all seven scenes at ${width}px; images loaded, 44px controls, dark theme, no clipped table/heading text or document overflow`);
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#all-steps').click();
  assert.equal(await page.locator('.scene:visible').count(),7);
  assert.equal(await page.locator('#purchase-cake').isChecked(),true);
  assert.equal((await page.evaluate(()=>retailStory.getState())).playing,false);
  const printed=await page.pdf({path:path.join(output,'all-steps.pdf'),printBackground:true,preferCSSPageSize:true});
  assert.equal([...printed.toString('latin1').matchAll(/\/Type\s*\/Page\b/g)].length,7);
  await page.locator('#walkthrough').click();
  assert.equal(await page.locator('.scene:visible').count(),1);
  await page.locator('#restart').click();
  await page.locator('#play').focus();
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'next');
  await page.locator('body').click({position:{x:5,y:5}});
  await page.keyboard.press('ArrowRight');
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,1);
  await page.keyboard.press('ArrowLeft');
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,0);
  await page.locator('#play').click();
  await page.clock.runFor(19000);
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,1);
  await page.locator('#play').click();
  const paused=await page.evaluate(()=>retailStory.getState().elapsed);
  await page.clock.runFor(5000);
  assert.equal(await page.evaluate(()=>retailStory.getState().elapsed),paused);
  await page.locator('#restart').click();
  await page.locator('#speed').selectOption('2');
  await page.locator('#play').click();
  await page.clock.runFor(1000);
  assert.equal(await page.evaluate(()=>retailStory.getState().elapsed),2000);
  await page.locator('#play').click();
  await page.locator('#speed').selectOption('1');
  await page.locator('[data-step="5"]').click();
  await page.locator('#play').click();
  await page.clock.runFor(12900);
  assert.equal(await page.locator('#purchase-cake').isChecked(),false);
  await page.clock.runFor(200);
  assert.equal(await page.locator('#purchase-cake').isChecked(),true);
  await page.clock.runFor(38000);
  const finished=await page.evaluate(()=>retailStory.getState());
  assert.equal(finished.elapsed,173000);
  assert.equal(finished.current,6);
  assert.equal(finished.playing,false);
  await page.locator('#play').click();
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,0);
  await page.locator('#play').click();
  await page.locator('#seek').fill('42000');
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,2);
  assert.equal((await page.evaluate(()=>retailStory.getState())).playing,false);
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.locator('#next').click();
  await page.clock.runFor(300);
  assert.equal((await page.evaluate(()=>retailStory.getState())).current,3);
  assert.deepEqual(errors,[]);
  assert.deepEqual(requests,[]);
  console.log('PASS: purchase/undo, unchanged model, all-steps/print, keyboard navigation, timed playback, pause, speed, auto-purchase, completion/replay, seek, reduced/normal motion; no errors or HTTP requests');
  console.log(`Screenshots and print preview: ${output}`);
} finally {await browser.close();}