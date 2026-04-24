# Claude Code Spinner Tips

Live list of the spinner tips shipped with [Claude Code](https://claude.com/code), extracted from the installed CLI binary.

**View: https://smartmanoj.github.io/ClaudeCodeTips/**

Updated daily via GitHub Actions against the latest release of Claude Code.

## Files

- `index.html` — the rendered page
- `tips.json` — the raw extracted tips (id, contents, cooldown)
- `extract_tips.py` — pulls the tips array out of the Claude Code binary's embedded JS bundle
- `generate_html.py` — renders `tips.json` + the current version into `index.html`

## Disable tips in your own Claude Code

Add to `~/.claude/settings.json`:

```json
{ "spinnerTipsEnabled": false }
```
