import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.DEMO_BROWSER_CHANNEL?{channel:process.env.DEMO_BROWSER_CHANNEL}:{})});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8780');
 await page.locator('#refresh:enabled').waitFor();
 await page.locator('#refresh').click();
 await page.locator('#rows tbody tr').first().waitFor();
 assert.equal(await page.locator('#rows tbody tr').count(),12);
 await page.locator('#region').selectOption('演示东区');
 await page.waitForFunction(()=>document.querySelectorAll('#rows tbody tr').length===4);
 await page.getByText('数据依据：合约个数加权完成率',{exact:true}).click();
 assert.ok((await page.locator('#evidence').innerText()).includes('参与 4 条记录'));
 await page.screenshot({path:'.demo-data/desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=390));
 await page.screenshot({path:'.demo-data/mobile.png',fullPage:true});
 for(const scenario of ['auth_failure','validation_failure','storage_failure']){
  await page.locator('#scenario').selectOption(scenario);await page.locator('#refresh').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('刷新失败'));
  await page.locator('#refresh:enabled').waitFor();
  assert.equal(await page.locator('#analysisSection').isVisible(),false);
  await page.locator('#history').click();
  await page.locator('#analysisSection').waitFor();
  assert.ok((await page.locator('#scope').innerText()).includes('历史成功快照，不代表本次刷新成功'));
 }
 await page.locator('#scenario').selectOption('empty');await page.locator('#refresh').click();
 await page.waitForFunction(()=>document.querySelector('#scope').textContent.includes('当前 0/0 条'));
 assert.equal(await page.locator('#rows tbody tr').count(),0);
 assert.ok((await page.locator('#metrics').innerText()).includes('不计算'));
 assert.deepEqual(errors,[]);
 console.log('Browser passed: success, filtered evidence, 3 failures, explicit history, empty, desktop/mobile.');
}finally{await browser.close()}
