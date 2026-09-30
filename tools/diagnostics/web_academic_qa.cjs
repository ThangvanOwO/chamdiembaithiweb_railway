/* Browser verification against local Django, plus isolated authenticated template fixtures.
   NODE_PATH may point at the bundled runtime's node_modules. No real submissions are sent. */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const out = path.join(root, 'scratch/web_academic_qa');
const origin = process.env.GRADEFLOW_QA_URL || 'http://127.0.0.1:8013';
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const results = [];
  try {
    for (const width of [1440, 768, 390, 360]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      for (const [name, url] of [['login','/accounts/login/'], ['register','/accounts/register/'], ['home','/'], ['guide','/huong-dan/'], ['download','/tai-ung-dung/']]) {
        await page.goto(origin + url, { waitUntil: 'networkidle' });
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        assert.equal(overflow, false, `${name}: overflow at ${width}`);
        assert.equal(await page.locator('video,input[capture]').count(), 0);
        await page.screenshot({ path: path.join(out, `${name}-${width}.png`), fullPage: true });
        results.push({page:name,width,overflow,errors:[...errors]});
      }
      if (width < 800) {
        await page.locator('.mobile-nav summary').click();
        assert.equal(await page.locator('.mobile-nav nav').isVisible(), true);
        await page.locator('.mobile-nav nav').getByRole('link', { name:'Hướng dẫn', exact:true }).click();
        assert.equal(new URL(page.url()).pathname, '/huong-dan/');
      }
      for (const name of ['dashboard', 'upload', 'import', 'exams']) {
        const url = `${origin}/__ui_fixture__/${name}/`;
        await page.route(url, route => route.fulfill({contentType:'text/html; charset=utf-8',body:fs.readFileSync(path.join(out, `${name}.html`),'utf8')}));
        // The dashboard chart is not the subject of UI rendering or a network dependency.
        await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({contentType:'application/javascript',body:'window.Chart=class {constructor(){}};'}));
        await page.goto(url, {waitUntil:'networkidle'});
        await page.locator('.sidebar').waitFor({state:'attached'});
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        if (overflow) {
          await page.screenshot({path:path.join(out,`${name}-${width}-overflow.png`),fullPage:true});
          console.log(await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el => {
            const rect=el.getBoundingClientRect(); return rect.width && rect.right > innerWidth + 1;
          }).map(el=>({tag:el.tagName,cls:el.className,width:el.getBoundingClientRect().width})).slice(0,20)));
        }
        assert.equal(overflow,false,`${name}: overflow at ${width}`);
        assert.equal(await page.locator('video,input[capture]').count(),0);
        if (name === 'dashboard') {
          const stats = await page.locator('.stat-card').evaluateAll(cards => cards.map(card => getComputedStyle(card).opacity));
          assert.deepEqual(stats, ['1','1','1','1'], 'Reduced motion must not hide dashboard statistics');
        }
        if (name === 'upload') {
          await page.locator('#upload-images').setInputFiles({name:'qa-blank.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBfQAAAAASUVORK5CYII=','base64')});
          assert.equal(await page.locator('.file-item-name').innerText(),'qa-blank.png');
          await page.locator('.file-item-remove').click();
          assert.equal(await page.locator('.file-item').count(),0);
        }
        if (name === 'import') {
          await page.locator('.import-dropzone').waitFor({state:'visible'});
          await page.route('**/grading/api/parse-image/', route => route.fulfill({json:{success:false,error:'Thông báo kiểm thử: ảnh chưa rõ'}}));
          await page.locator('input[type=file]').setInputFiles({name:'qa.png',mimeType:'image/png',buffer:Buffer.from('test')});
          await page.getByText('Thông báo kiểm thử: ảnh chưa rõ',{exact:true}).waitFor();
        }
        if (width < 768) {
          await page.locator('.mobile-menu-btn').click();
          assert.match(await page.locator('.sidebar').getAttribute('class'),/mobile-open/);
          await page.keyboard.press('Escape');
          assert.doesNotMatch(await page.locator('.sidebar').getAttribute('class'),/mobile-open/);
        }
        await page.screenshot({path:path.join(out,`${name}-${width}.png`),fullPage:true});
        results.push({page:name,width,overflow,errors:[...errors]});
      }
      assert.deepEqual(errors,[],`JS errors at width ${width}`);
      await context.close();
    }
    fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
    console.log(`PASS: ${results.length} page/viewport combinations; keyboard navigation, upload/remove, mocked import error. No real records created.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
