import {expect,test} from "@playwright/test";

test("management navigation keeps one mounted frame, theme and experiment context",async({page})=>{
  await page.goto("/sandbox?mode=demo&projectId=42&studyId=study-context&workflowId=workflow-context");
  const shell=page.locator('[data-app-shell="workspace"]');
  await expect(page.getByRole("heading",{name:"多 Agent 隐蔽通信检测与干预实验平台",exact:true})).toBeVisible();
  await shell.evaluate(el=>el.setAttribute("data-retained-frame","yes"));
  const nav=page.getByRole("navigation",{name:"主导航",exact:true});
  for(const [label,path] of [["项目管理","projects"],["证据与报告","reports"],["安全调查","investigations"],["系统与诊断","system-overview"]]){
    await nav.getByRole("link",{name:label,exact:true}).click();
    await expect(page).toHaveURL(new RegExp(`/${path}$`));
    await expect(shell).toHaveAttribute("data-retained-frame","yes");
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.locator(".stego-brand")).toHaveCount(1);
    await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
    await expect.poll(()=>shell.evaluate(el=>getComputedStyle(el).backgroundColor)).toBe("rgb(8, 14, 25)");
    for(const size of [{width:1440,height:900},{width:1024,height:768},{width:390,height:844}]){
      await page.setViewportSize(size);
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:test.info().outputPath(`${path}-${size.width}.png`),fullPage:true});
    }
    await page.setViewportSize({width:1440,height:900});
  }
  await nav.getByRole("link",{name:"通信检测台",exact:true}).click();
  await expect(page).toHaveURL(/\/detection\?/);
  const query=new URL(page.url()).searchParams;
  expect(query.get("projectId")).toBe("42");expect(query.get("studyId")).toBe("study-context");expect(query.get("workflowId")).toBe("workflow-context");
  await expect(page.locator(".top-context .source-badge")).toHaveText("DEMO");
  await expect(shell).toHaveAttribute("data-retained-frame","yes");
});

test("mobile navigation closes on Escape and route change and restores keyboard focus",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/sandbox?mode=demo");
  const inspector=page.getByRole("button",{name:"检视器",exact:true});await inspector.click();
  await expect(page.getByRole("dialog",{name:"上下文检视器"})).toBeVisible();
  await page.keyboard.press("Escape");await expect(page.getByRole("dialog",{name:"上下文检视器"})).toHaveCount(0);await expect(inspector).toBeFocused();
  const menu=page.getByRole("button",{name:"打开导航",exact:true});
  await menu.click();await expect(menu).toHaveAttribute("aria-expanded","true");
  await page.keyboard.press("Escape");await expect(menu).toHaveAttribute("aria-expanded","false");await expect(menu).toBeFocused();
  await menu.click();
  await page.getByRole("navigation",{name:"主导航",exact:true}).getByRole("link",{name:"项目管理",exact:true}).click();
  await expect(page.getByRole("heading",{name:"项目管理",exact:true})).toBeVisible();
  await expect(menu).toHaveAttribute("aria-expanded","false");
  await expect.poll(()=>page.evaluate(()=>document.body.style.overflow)).not.toBe("hidden");
  await expect(page.locator("main")).toBeFocused();
});

test("resource pages do not silently request sample ids and Demo research cannot register",async({page})=>{
  const sampleReads:string[]=[];const writes:string[]=[];
  page.on("request",request=>{if(/(?:run|inv)-qwb-000[125]/.test(request.url()))sampleReads.push(request.url());if(request.method()==="POST"&&request.url().includes("/studies"))writes.push(request.url());});
  for(const path of ["reports","evidence","findings","hypotheses","defenses"]){
    await page.goto(`/${path}`);await expect(page.getByText(/尚未选择.*ID/)).toBeVisible();
    await expect(page.getByRole("button",{name:"载入记录",exact:true})).toBeDisabled();
  }
  expect(sampleReads).toEqual([]);
  await page.goto("/research?mode=demo");
  await expect(page.getByRole("heading",{name:"研究管理",exact:true})).toBeVisible();
  await expect(page.locator(".research-config")).toHaveCount(0);
  await expect(page.getByRole("button",{name:"确认并登记 Study"})).toHaveCount(0);
  expect(writes).toEqual([]);
  await page.goto("/research?projectId=0&studyId=&workflowId=");
  await page.getByText("研究工作台 · 预注册与高级配置",{exact:true}).click();
  await expect(page.getByText("请先选择项目，再登记研究配置。",{exact:true})).toBeVisible();
  await expect(page.getByLabel("冻结研究配置 JSON")).toHaveCount(0);
  await page.goto("/a-page-that-does-not-exist");
  await expect(page.getByRole("heading",{name:"页面不存在"})).toBeVisible();await expect(page.locator('[data-app-shell]')).toHaveCount(1);
});
