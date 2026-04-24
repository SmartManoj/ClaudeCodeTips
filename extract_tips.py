"""Extract spinner tips from a `strings`-dump of the Claude Code binary.

Usage: python extract_tips.py <strings.txt> [tips.json]
"""
import re, json, sys

BACKSLASH = chr(92)

def scan_array_from(data, start):
    depth = 1
    i = start
    in_str = None
    esc = False
    while i < len(data) and depth > 0:
        c = data[i]
        if esc:
            esc = False
        elif in_str:
            if c == BACKSLASH:
                esc = True
            elif c == in_str:
                in_str = None
        else:
            if c in ('"', "'", '`'):
                in_str = c
            elif c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
        i += 1
    return data[start:i-1]

def find_tips_array(data):
    """Find the tips array by locating a known-stable tip id and walking back
    to the enclosing `[`. Avoids relying on the minified array identifier."""
    marker = re.search(r'id:"new-user-warmup"', data)
    if not marker:
        return None
    # Walk backward from the marker to find the containing `[`
    pos = marker.start()
    depth = 0
    i = pos
    while i > 0:
        c = data[i]
        if c == ']':
            depth += 1
        elif c == '[':
            if depth == 0:
                return scan_array_from(data, i + 1)
            depth -= 1
        i -= 1
    return None

def split_objects(body):
    chunks = []
    d = 0
    buf = []
    in_s = None
    es = False
    for ch in body:
        if es:
            es = False
            buf.append(ch); continue
        if in_s:
            if ch == BACKSLASH: es = True
            elif ch == in_s: in_s = None
            buf.append(ch); continue
        if ch in ('"',"'",'`'):
            in_s = ch; buf.append(ch); continue
        if ch == '{':
            if d == 0: buf = ['{']
            else: buf.append(ch)
            d += 1
        elif ch == '}':
            d -= 1
            buf.append(ch)
            if d == 0:
                chunks.append(''.join(buf))
                buf = []
        else:
            if d > 0: buf.append(ch)
    return chunks

def decode_js_string(s):
    try:
        return bytes(s, 'utf-8').decode('unicode_escape')
    except Exception:
        return s

def extract_content(chunk):
    m = re.search(r'content\s*:\s*async[^=]*=>\s*"((?:[^"\\]|\\.)*)"', chunk)
    if m: return [decode_js_string(m.group(1))]
    m = re.search(r"content\s*:\s*async[^=]*=>\s*'((?:[^'\\]|\\.)*)'", chunk)
    if m: return [decode_js_string(m.group(1))]
    m = re.search(r'content\s*:\s*async[^=]*=>\s*`([^`]*)`', chunk)
    if m: return [decode_js_string(m.group(1))]
    m = re.search(r'content\s*:\s*async[^?]+\?\s*"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"', chunk)
    if m: return [decode_js_string(m.group(1)), decode_js_string(m.group(2))]
    cblock = chunk
    cpos = cblock.find('content:')
    if cpos >= 0:
        cblock = cblock[cpos:]
    m = re.search(r'return\s+`([^`]*)`', cblock)
    if m: return [decode_js_string(m.group(1))]
    m = re.search(r'return\s+"((?:[^"\\]|\\.)*)"', cblock)
    if m: return [decode_js_string(m.group(1))]
    m = re.search(r'\?\s*`([^`]*)`\s*:\s*`([^`]*)`', chunk)
    if m: return [decode_js_string(m.group(1)), decode_js_string(m.group(2))]
    return []

def collect_bindings(chunk):
    """Find `let X=<styler>("suggestion"|"claude",H.theme)("VAL")` style bindings.

    The styler function has varied minified names across builds ($$, qq, etc.)
    so we match any identifier (not a reserved control-flow keyword).
    """
    bindings = {}
    pattern = (
        r'(?:let|const|var)\s+([A-Za-z_$][A-Za-z_$0-9]*)\s*=\s*'
        r'[A-Za-z_$][A-Za-z_$0-9]*\(\s*"(?:suggestion|claude)"\s*,\s*[A-Za-z_$][A-Za-z_$0-9]*\.theme\s*\)'
        r'\(\s*"([^"]+)"\s*\)'
    )
    for m in re.finditer(pattern, chunk):
        bindings[m.group(1)] = m.group(2)
    return bindings

def clean_tip(s, bindings=None):
    bindings = bindings or {}
    # Resolve `${<var>}` from bindings (before other substitutions)
    def _resolve(m):
        name = m.group(1)
        return bindings.get(name, '[…]')
    s = re.sub(r'\$\{([A-Za-z_$][A-Za-z_$0-9]*)\}', _resolve, s)
    # Template-wrapped styler calls: ${<styler>("suggestion"|"claude", theme)("X")} → X
    styler_call = r'[A-Za-z_$][A-Za-z_$0-9]*\(\s*"(?:suggestion|claude)"\s*,\s*[A-Za-z_$][A-Za-z_$0-9]*\.theme\s*\)'
    s = re.sub(r'\$\{\s*' + styler_call + r'\(\s*"([^"]+)"\s*\)\s*\}', r'\1', s)
    s = re.sub(r'\$\{\s*' + styler_call + r'\(\s*`([^`]+)`\s*\)\s*\}', r'\1', s)
    # Bare styler calls: <styler>("suggestion"|"claude", theme)("X") → X
    s = re.sub(styler_call + r'\(`?([^)`]*?)`?\)', r'\1', s)
    # Link helper: ${Hp("URL","TEXT")} → TEXT
    s = re.sub(r'\$\{Hp\(\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)\}', r'\1', s)
    # Variable-referenced styler: ${q("X")} or ${q('X')} or ${q(`X`)} → X
    # Handle double-quoted inner, single-quoted inner, backtick inner, and nested-quote cases.
    s = re.sub(r'''\$\{[A-Za-z_$][A-Za-z_$0-9]*\(\s*"((?:[^"\\]|\\.)*)"\s*\)\}''', r'\1', s)
    s = re.sub(r"""\$\{[A-Za-z_$][A-Za-z_$0-9]*\(\s*'((?:[^'\\]|\\.)*)'\s*\)\}""", r'\1', s)
    s = re.sub(r'\$\{[A-Za-z_$][A-Za-z_$0-9]*\(\s*`([^`]+)`\s*\)\}', r'\1', s)
    # Keyboard shortcuts: ${<PP>("chat:action","Chat","keybinding")} → keybinding
    s = re.sub(
        r'\$\{[A-Za-z_$][A-Za-z_$0-9]*\(\s*"[^"]+"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)\}',
        r'\1', s)
    # Anything else
    s = re.sub(r'\$\{[^{}]*\}', '[…]', s)
    s = s.replace(r'\\n', '\n').replace(r'\n', '\n')
    return s.strip()

# Contextual tips not stored in the tips array — they're hardcoded in the
# spinner render path and fire based on session state rather than selection.
CONTEXTUAL_TIPS = [
    {
        'id': 'clear-when-topic-switch',
        'contents': ['Use /clear to start fresh when switching topics and free up context'],
        'cooldown': None,
        'condition': 'shown after session exceeds 30 minutes',
    },
    {
        'id': 'btw-for-side-questions',
        'contents': ["Use /btw to ask a quick side question without interrupting Claude's current work"],
        'cooldown': None,
        'condition': "shown after 30 seconds if /btw hasn't been used yet",
    },
]

POST_PROCESS = {
    # ${Zq.terminal==="vscode"?"code":Zq.terminal} — IDE-family terminals
    'vscode-command-install': [('[…]', '<your editor>')],
    # ${q(eYH($))} — formatted referral amount
    'guest-passes': [('earn […] of', 'earn')],
}

MANUAL_FALLBACKS = {
    'team-artifacts': '(dynamic) Summary of team artifacts available to Claude',
    'desktop-shortcut': 'Continue your session in Claude Code Desktop with /desktop',
    'remote-control': 'Control this session from the Claude mobile app · run /remote-control',
    'push-notif': 'Get pinged on your phone when long tasks finish · enable push notifications in /config',
    'frontend-design-plugin': 'Working with HTML/CSS? Install the frontend-design plugin: /plugin install frontend-design@<version>',
    'vercel-plugin': 'Working with Vercel? Install the vercel plugin: /plugin install vercel@<version>',
    'overage-credit': '<amount> in extra usage, on us · third-party apps · /extra-usage',
}

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    strings_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'tips.json'

    with open(strings_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = f.read()

    body = find_tips_array(data)
    if body is None:
        print("ERROR: could not locate tips array (marker 'new-user-warmup' not found).", file=sys.stderr)
        sys.exit(2)

    chunks = split_objects(body)
    debug = '--debug-unresolved' in sys.argv
    tips = []
    for ch in chunks:
        id_m = re.search(r'id\s*:\s*"([^"]+)"', ch)
        cd_m = re.search(r'cooldownSessions\s*:\s*(\d+)', ch)
        contents = extract_content(ch)
        bindings = collect_bindings(ch)
        contents = [clean_tip(c, bindings) for c in contents if c and len(c.strip()) > 0]
        tid = id_m.group(1) if id_m else '?'
        if not contents and tid in MANUAL_FALLBACKS:
            contents = [MANUAL_FALLBACKS[tid]]
        if tid in POST_PROCESS:
            for find, replace in POST_PROCESS[tid]:
                contents = [c.replace(find, replace) for c in contents]
        if debug and any('[…]' in c for c in contents):
            print(f"\n--- UNRESOLVED: {tid} ---", file=sys.stderr)
            print(f"bindings: {bindings}", file=sys.stderr)
            print(f"raw: {ch}", file=sys.stderr)
        tips.append({
            'id': tid,
            'cooldown': int(cd_m.group(1)) if cd_m else None,
            'contents': contents,
        })

    # Append contextual tips if their trigger strings are still present in the bundle
    for ctx in CONTEXTUAL_TIPS:
        if any(c in data for c in ctx['contents']):
            tips.append(ctx)

    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(tips, f, indent=2, ensure_ascii=False)
        f.write('\n')

    missing = [t['id'] for t in tips if not t['contents']]
    print(f"Extracted {len(tips)} tips to {out_path}")
    if missing:
        print(f"  {len(missing)} without static content: {missing}")

if __name__ == '__main__':
    main()
