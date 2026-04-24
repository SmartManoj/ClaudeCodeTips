"""Render tips.json + a version string into index.html.

Usage: python generate_html.py <version> [tips.json] [index.html]
"""
import json, html, sys, datetime

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    version = sys.argv[1]
    tips_path = sys.argv[2] if len(sys.argv) > 2 else 'tips.json'
    out_path = sys.argv[3] if len(sys.argv) > 3 else 'index.html'

    with open(tips_path, 'r', encoding='utf-8') as f:
        tips = json.load(f)

    tips_sorted = sorted(tips, key=lambda t: t['id'].lower())
    rows = []
    for i, t in enumerate(tips_sorted, 1):
        tid = html.escape(t['id'])
        if t['contents']:
            body = '<br><span class="alt">or</span><br>'.join(
                html.escape(c).replace('\n', '<br>') for c in t['contents']
            )
        else:
            body = '<em class="dyn">(dynamic — content generated at runtime)</em>'
        if t.get('condition'):
            body += f'<br><span class="cond">{html.escape(t["condition"])}</span>'
        rows.append(f'''    <tr>
      <td class="num">{i}</td>
      <td class="id"><code>{tid}</code></td>
      <td class="tip">{body}</td>
    </tr>''')

    today = datetime.date.today().isoformat()
    html_doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Claude Code — Spinner Tips ({html.escape(version)})</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font: 15px/1.55 -apple-system, 'Segoe UI', Roboto, sans-serif; max-width: 920px; margin: 2em auto; padding: 0 1em; color: #222; }}
  header {{ border-bottom: 1px solid #ddd; padding-bottom: .8em; margin-bottom: 1.2em; }}
  h1 {{ margin: 0 0 .2em; font-size: 1.6em; }}
  .version {{ display: inline-block; background: #eee; padding: .15em .55em; border-radius: 4px; font-family: ui-monospace, Consolas, monospace; font-size: .9em; }}
  .meta {{ color: #666; font-size: .9em; margin-top: .4em; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: .55em .7em; border-bottom: 1px solid #eee; vertical-align: top; }}
  th {{ background: #fafafa; font-weight: 600; font-size: .85em; text-transform: uppercase; letter-spacing: .04em; color: #555; }}
  td.num {{ color: #888; width: 2em; }}
  td.id code {{ font-size: .85em; color: #444; background: #f4f4f4; padding: .05em .4em; border-radius: 3px; }}
  td.id {{ width: 16em; }}
  .alt {{ color: #999; font-size: .85em; font-style: italic; }}
  .cond {{ color: #999; font-size: .82em; font-style: italic; display: inline-block; margin-top: .25em; }}
  .dyn {{ color: #aa7; }}
  footer {{ margin-top: 2em; color: #888; font-size: .85em; }}
  code {{ font-family: ui-monospace, Consolas, monospace; }}
  a {{ color: #36c; }}
</style>
</head>
<body>
<header>
  <h1>Claude Code — Spinner Tips</h1>
  <div><span class="version">{html.escape(version)}</span></div>
  <div class="meta">{len(tips)} tips extracted from the installed binary, sorted by ID. Last updated {today}.</div>
</header>
<table>
  <thead><tr><th>#</th><th>ID</th><th>Tip</th></tr></thead>
  <tbody>
{chr(10).join(rows)}
  </tbody>
</table>
<footer>
  Set <code>spinnerTipsEnabled: false</code> in <code>~/.claude/settings.json</code> to hide these.
  Override with <code>spinnerTipsOverride</code>. Source: <a href="https://github.com/SmartManoj/ClaudeCodeTips">github.com/SmartManoj/ClaudeCodeTips</a>.
</footer>
</body>
</html>
'''

    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html_doc)

    print(f"Wrote {out_path} ({len(tips)} tips, version {version})")

if __name__ == '__main__':
    main()
