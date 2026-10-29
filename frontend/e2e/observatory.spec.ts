import {expect,test} from "@playwright/test";

test("new workbench separates Demo from writes and previews all intervention methods",async({page})=>{
  const posts:string[]=[];
  page.on("request",request=>{if(request.method()==="POST"&&/studies/.test(request.url()))posts.push(request.url());});
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  await page.goto("/intervention-lab?mode=demo");
  await expect(page.getByRole("heading",{name:"干预实验台",exact:true})).toBeVisible();
  await expect(page.getByText("DEMO · 预置示意场景，非实测",{exact:true})).toBeVisible();
  for(const name of ["Agent 隔离","消息阻断","消息替换","LEACE 表示擦除","Activation Patching"]){
    await page.locator(".method-list").getByRole("button",{name,exact:false}).click();
    await page.getByRole("button",{name:"预览效果",exact:true}).click();
    await expect(page.getByText("PREVIEW · 未运行",{exact:true}).first()).toBeVisible();
    await expect(page.getByRole("button",{name:"提交冻结实验臂",exact:true})).toBeDisabled();
    await page.getByRole("button",{name:"撤销预览",exact:true}).click();
  }
  expect(posts).toEqual([]);expect(errors).toEqual([]);
});

test("five product pages are usable at all required viewport sizes",async({page})=>{
  for(const route of ["sandbox","detection","intervention-lab","analysis","research"]){
    await page.goto(`/${route}?mode=demo`);
    await expect(page.locator(".desk-title h1")).toBeVisible();
    for(const size of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:1024,height:768},{width:390,height:844}]){
      await page.setViewportSize(size);
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if(["sandbox","detection","intervention-lab"].includes(route)){
        await expect.poll(()=>page.locator(".agent-canvas").first().evaluate(canvas=>{
          const outer=canvas.getBoundingClientRect();
          const nodes=Array.from(canvas.querySelectorAll(".react-flow__node"));
          return nodes.length>0&&nodes.every(node=>{const box=node.getBoundingClientRect();return box.left>=outer.left&&box.right<=outer.right&&box.top>=outer.top&&box.bottom<=outer.bottom;});
        })).toBe(true);
      }
      await page.screenshot({path:test.info().outputPath(`${route}-${size.width}.png`),fullPage:true});
    }
    if(route==="detection"){
      await page.getByRole("button",{name:"检视器",exact:true}).click();
      await expect(page.locator(".context-inspector")).toBeVisible();
      await page.getByRole("button",{name:"关闭检视器"}).click();
    }
    await page.setViewportSize({width:1440,height:900});
  }
  await page.goto("/");await expect(page).toHaveURL(/\/sandbox/);
});
