import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const filename=path.join(here,'backup/M6_Demo_Catalog_Onboarding.html');
const html=fs.readFileSync(filename,'utf8');
const data=JSON.parse(html.match(/<script id="catalog-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const capture=JSON.parse(fs.readFileSync(path.join(here,'capture.json'),'utf8'));
assert.ok(!/__DATA__|__PLOTLY__|__ICONS__/.test(html));
assert.ok(!/<(?:script|img|link)[^>]*(?:src|href)=["']https?:\/\//.test(html));
for(const script of html.matchAll(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/g))if(!(script[1]||'').includes('application/json'))new vm.Script(script[2]);
assert.equal(data.records.length,5);
assert.equal(data.records.reduce((total,record)=>total+record.reference_total,0),33);
assert.equal(data.records.filter(record=>record.route==='Human review').length,2);
assert.equal(data.records.filter(record=>record.route==='Hold').length,3);
assert.equal(data.records.filter(record=>record.photo_code).length,3);
assert.equal(data.records.filter(record=>record.photo).length,data.product_photos_included?3:0);
for(const record of data.records){assert.equal(record.raw_response,capture.records.find(row=>row.id===record.id).raw_response);assert.deepEqual(record.response,JSON.parse(record.raw_response));}
console.log('PASS: offline packaging, actual-capture parity, 33 field proposals, 2 review / 3 hold routes, embedded script syntax');
if(!process.env.PLAYWRIGHT_MODULE){console.log('Browser checks not run: set PLAYWRIGHT_MODULE.');process.exit(0);}
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE);
const output='/tmp/m6-catalog-demo-tests';fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
  const errors=[],requests=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  await page.route(/^https?:\/\//,route=>{requests.push(route.request().url());return route.abort();});
  await page.goto(pathToFileURL(filename).href);
  const inspect=async(label)=>{
    const result=await page.evaluate(()=>({
      overflow:document.documentElement.scrollWidth-innerWidth,
      images:[...document.images].every(image=>image.complete&&image.naturalWidth>0),
      buttons:[...document.querySelectorAll('button')].filter(button=>{const box=button.getBoundingClientRect();return box.height>0&&(box.height<44||box.width<44);}).map(button=>button.id||button.textContent),
      clipped:[...document.querySelectorAll('h1,h2,h3,td,th,p')].filter(element=>element.getClientRects().length&&element.scrollWidth>element.clientWidth+1).map(element=>element.textContent),
    }));
    assert.ok(result.overflow<=1,label+JSON.stringify(result));assert.ok(result.images,label);assert.deepEqual(result.buttons,[],label);assert.deepEqual(result.clipped,[],label);
  };
  for(const width of [1440,768,390]){
    await page.setViewportSize({width,height:1000});
    for(let record=0;record<5;record++){
      await page.locator(`[data-record="${record}"]`).click();
      for(let step=0;step<5;step++){
        await page.locator(`[data-step="${step}"]`).click();
        await inspect(`${width}px record${record} step${step}`);
        if(record===0&&[0,1,2,3,4].includes(step)&&width!==768)await page.screenshot({path:path.join(output,`record0-step${step}-${width}.png`),fullPage:true});
      }
      assert.equal(await page.locator('#approve').isDisabled(),true);
      if(data.records[record].route==='Hold')assert.ok(await page.locator('#ack').isDisabled());
    }
    await page.locator('#batch-view').click();
    await page.waitForFunction(()=>document.querySelectorAll('.js-plotly-plot').length===3&&[...document.querySelectorAll('.js-plotly-plot')].every(element=>element.querySelector('.main-svg')));
    await page.waitForFunction(()=>[...document.querySelectorAll('.js-plotly-plot')].every(element=>Math.abs(element._fullLayout.width-element.clientWidth)<2));
    assert.ok(await page.evaluate(()=>[...document.querySelectorAll('.js-plotly-plot')].every(element=>element._fullLayout.yaxis.type==='category'&&element._fullLayout.yaxis._categories.length===5)));
    assert.ok(await page.locator('#field-chart .heatmaplayer image').evaluateAll(images=>images.length>0&&images.every(image=>Number.isFinite(Number(image.getAttribute('height')))&&Number(image.getAttribute('height'))>0)));
    for(const id of ['status-chart','reference-chart'])assert.ok(await page.locator(`#${id}`).evaluate(element=>element.querySelector('.legend').getBoundingClientRect().bottom<=element.getBoundingClientRect().top+element._fullLayout._size.t+1),`${id}: legend overlaps plot`);
    await inspect(`batch/${width}`);
    assert.equal(await page.locator('#field-chart .heatmap-label').count(),50);
    await page.screenshot({path:path.join(output,`batch-${width}.png`),fullPage:true});
    await page.locator('#workflow-view').click();
    console.log(`PASS: ${width}px / five records x five stages, chart marks, images, touch targets and no overflow`);
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-record="0"]').click();await page.locator('[data-step="1"]').click();
  await page.getByRole('button',{name:'Evidence for Length (cm)',exact:true}).click();
  assert.match(await page.locator('#field-evidence').innerText(),/approximately 8 metres/);
  await page.locator('[data-step="4"]').click();await page.locator('#ack').check();await page.locator('#approve').click();
  assert.match(await page.locator('.decision').innerText(),/Approved \(demo\)/);
  await page.locator('[data-record="3"]').click();assert.ok(await page.locator('#approve').isDisabled());await page.locator('#hold').click();
  assert.match(await page.locator('.decision').innerText(),/Held \(demo\)/);
  const pending=page.waitForEvent('download');await page.locator('#export').click();const download=await pending;
  const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  assert.equal(exported.records[0].decision,'Approved (demo)');assert.equal(exported.records[3].decision,'Held (demo)');
  await page.locator('#undo-decision').click();assert.match(await page.locator('.decision').innerText(),/Not reviewed/);
  await page.locator('#reset').click();assert.deepEqual(await page.evaluate(()=>catalogDemo.getState().decisions),{});
  assert.equal(await page.locator('#previous').isDisabled(),true);await page.locator('#next').click();assert.equal((await page.evaluate(()=>catalogDemo.getState())).step,1);
  await page.locator('#previous').click();assert.equal((await page.evaluate(()=>catalogDemo.getState())).step,0);
  await page.locator('#batch-view').click();await page.locator('[data-open="4"]').click();assert.equal((await page.evaluate(()=>catalogDemo.getState())).selected,4);
  await page.locator('#reset').click();
  assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
  console.log('PASS: source drilldown, gated approval, hold, undo, reset, review export, next/back, batch navigation; zero HTTP or browser errors.');
}finally{await browser.close();}