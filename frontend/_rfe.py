import os

out = open("_fe.log", "w", encoding="utf-8")
for name in ("tc.log", "lint.log", "vt.log", "bd.log"):
    if os.path.exists(name):
        out.write(f"=== {name} ===\n")
        out.write(open(name, encoding="utf-8", errors="replace").read()[-1200:])
    else:
        out.write(f"{name} MISSING\n")
out.close()
print("ok")
