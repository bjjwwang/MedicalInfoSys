#!/usr/bin/env python3
"""Generate a Word-style track-changes review page from the git diff
between two revisions, for the docs/*.html files. HTML tags are stripped
so only the readable Chinese copy is shown."""
import subprocess, re, difflib, html, sys

OLD = sys.argv[1] if len(sys.argv) > 1 else "0c0a0ff"
NEW = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

FRIENDLY = {
    "docs/index.html": "首页 index.html",
    "docs/01-项目概述.html": "01 项目概述",
    "docs/02-商业模式与团队规划.html": "02 商业模式与团队规划",
    "docs/03-技术架构与数据库设计.html": "03 技术架构与数据库设计",
    "docs/04-功能模块设计.html": "04 功能模块设计",
    "docs/05-开发迭代路线图.html": "05 开发迭代路线图",
    "docs/06-合规与安全规范.html": "06 合规与安全规范",
    "docs/07-运营与风险管理.html": "07 运营与风险管理",
    "docs/demo.html": "流程原型 Demo (demo.html)",
    "docs/revenue-mechanism-thoughts-slides.html": "分润 Slides",
    "docs/quotation-minimal.html": "新版 Lean MVP (quotation-minimal.html)",
}

def sh(args):
    return subprocess.check_output(args).decode("utf-8")

def get(rev, path):
    try:
        return sh(["git", "show", f"{rev}:{path}"])
    except subprocess.CalledProcessError:
        return ""

def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&yen;", "¥").replace("&uarr;", "↑").replace("&rarr;", "→")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

files = [f for f in sh(["git", "-c", "core.quotepath=false", "diff", "--name-only", OLD, NEW, "--", "docs"]).split("\n") if f.strip()]

sections = []
total_changes = 0
for f in files:
    old = get(OLD, f).splitlines()
    new = get(NEW, f).splitlines()
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        dels = [strip_tags(l) for l in old[i1:i2]]
        dels = [d for d in dels if d]
        adds = [strip_tags(l) for l in new[j1:j2]]
        adds = [a for a in adds if a]
        if not dels and not adds:
            continue
        total_changes += 1
        rows = []
        for d in dels:
            rows.append(f'<p class="row"><span class="tag-del">删</span><del>{html.escape(d)}</del></p>')
        for a in adds:
            rows.append(f'<p class="row"><span class="tag-ins">增</span><ins>{html.escape(a)}</ins></p>')
        blocks.append('<div class="change">' + "".join(rows) + "</div>")
    if blocks:
        title = FRIENDLY.get(f, f)
        sections.append(
            f'<section class="file"><h2>{html.escape(title)} '
            f'<span class="count">{len(blocks)} 处改动</span></h2>{"".join(blocks)}</section>'
        )

CSS = """
:root{--bg:#f7f5ef;--paper:#fff;--ink:#1f2a37;--muted:#667085;--line:#d9dee8;
--del:#c2414e;--del-bg:#fdeef0;--ins:#1f7a4d;--ins-bg:#e9f7ef;--accent:#315fbd;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif;}
.wrap{max-width:920px;margin:0 auto;padding:32px 20px 80px;}
.hero{background:var(--paper);border:1px solid var(--line);border-radius:14px;
padding:24px 26px;box-shadow:0 14px 34px rgba(31,42,55,.10);margin-bottom:22px;}
.hero h1{margin:0 0 8px;font-size:26px;}
.hero p{margin:6px 0;color:var(--muted);}
.legend{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;}
.legend span{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;
padding:5px 10px;border-radius:999px;border:1px solid var(--line);background:#fafbfc;}
.dot{width:11px;height:11px;border-radius:3px;display:inline-block;}
.dot.d{background:var(--del-bg);border:1px solid var(--del);}
.dot.i{background:var(--ins-bg);border:1px solid var(--ins);}
nav.toc{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin-bottom:22px;}
nav.toc b{display:block;margin-bottom:8px;}
nav.toc a{display:inline-block;margin:3px 10px 3px 0;color:var(--accent);text-decoration:none;font-weight:600;font-size:14px;}
section.file{background:var(--paper);border:1px solid var(--line);border-radius:14px;
padding:20px 24px;margin-bottom:18px;box-shadow:0 10px 26px rgba(31,42,55,.07);scroll-margin-top:16px;}
section.file h2{margin:0 0 14px;font-size:20px;border-bottom:1px solid var(--line);padding-bottom:10px;
display:flex;align-items:baseline;justify-content:space-between;gap:12px;}
.count{font-size:13px;color:var(--muted);font-weight:600;white-space:nowrap;}
.change{border-left:3px solid var(--line);padding:6px 0 6px 14px;margin:14px 0;}
.row{margin:5px 0;display:flex;gap:8px;align-items:flex-start;}
.tag-del,.tag-ins{flex:0 0 auto;margin-top:3px;font-size:11px;font-weight:800;color:#fff;
border-radius:5px;padding:1px 6px;line-height:1.5;}
.tag-del{background:var(--del);}
.tag-ins{background:var(--ins);}
del{color:var(--del);background:var(--del-bg);text-decoration:line-through;
text-decoration-color:var(--del);border-radius:4px;padding:1px 4px;}
ins{color:var(--ins);background:var(--ins-bg);text-decoration:none;border-radius:4px;padding:1px 4px;}
footer{color:var(--muted);font-size:13px;text-align:center;margin-top:24px;}
footer code{background:#eceff3;padding:2px 6px;border-radius:5px;}
"""

toc = "".join(
    f'<a href="#f{i}">{re.sub(r"<[^>]+>","",s.split("</h2>")[0].split(">")[-1]) if False else FRIENDLY.get(files[i], files[i])}</a>'
    for i, s in enumerate(sections)
) if False else ""
# simple TOC from FRIENDLY order actually present
present = [f for f in files if any(FRIENDLY.get(f, f) in sec for sec in sections)]
toc_links = []
indexed_sections = []
for idx, f in enumerate(files):
    title = FRIENDLY.get(f, f)
    matching = [s for s in sections if f">{html.escape(title)} " in s]
    if matching:
        anchor = f"f{idx}"
        toc_links.append(f'<a href="#{anchor}">{html.escape(title)}</a>')
        indexed_sections.append(matching[0].replace('<section class="file">', f'<section class="file" id="{anchor}">', 1))

page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>改动审阅（Word Review 模式）</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<div class="hero">
<h1>改动审阅：数据资产重新立为底层主线</h1>
<p>按 Word 修订模式展示两次提交之间的删改痕迹。<del>红色删除线</del> 是删掉的旧文案，<ins>绿色高亮</ins> 是新增/替换后的文案。已隐去 HTML 标签，仅显示正文。</p>
<p>对比区间：<code>{OLD}</code> → <code>{NEW}</code>　共 {total_changes} 处文案改动，覆盖 {len(indexed_sections)} 个文件。</p>
<div class="legend"><span><i class="dot d"></i>删除（旧）</span><span><i class="dot i"></i>新增（新）</span></div>
</div>
<nav class="toc"><b>跳转</b>{''.join(toc_links)}</nav>
{''.join(indexed_sections)}
<footer>本页由 <code>scripts/gen_review.py</code> 从 git diff 自动生成。如需重新生成：<code>python3 scripts/gen_review.py {OLD} HEAD</code></footer>
</div></body></html>
"""

with open("docs/changes-review.html", "w", encoding="utf-8") as fp:
    fp.write(page)
print(f"wrote docs/changes-review.html: {total_changes} changes across {len(indexed_sections)} files")
