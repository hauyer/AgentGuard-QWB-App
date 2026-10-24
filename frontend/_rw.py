t = open("src/pages/__tests__/investigations.test.tsx", encoding="utf-8").read()
idx = t.find("function renderListPage")
if idx < 0:
    idx = t.find("vi.spyOn")
out = open("_w.log", "w", encoding="utf-8")
out.write(t[idx:idx + 2800])
out.close()
print("ok")
