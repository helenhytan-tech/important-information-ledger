#!/usr/bin/env python3
"""Create the deployable static site without copying local data or server code."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
FILES = ("index.html", "app.js", "core.js", "styles.css")

DIST.mkdir(exist_ok=True)
for path in DIST.iterdir():
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
for name in FILES:
    shutil.copy2(ROOT / name, DIST / name)
(DIST / "index.html").write_text(
    (DIST / "index.html").read_text(encoding="utf-8")
    .replace('href="/styles.css"', 'href="styles.css"')
    .replace('src="/core.js"', 'src="core.js"')
    .replace('src="/app.js"', 'src="app.js"'),
    encoding="utf-8",
)
(DIST / ".nojekyll").write_text("", encoding="utf-8")
print(f"已生成静态部署目录：{DIST}")
print("只包含网页文件，不包含 data/、server.py 或本机记录。")
