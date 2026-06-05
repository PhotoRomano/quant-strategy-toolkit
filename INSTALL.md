# Installing the skills

Claude skills are just folders containing a `SKILL.md`. There's no build step and no account needed.

## Claude Code (terminal / IDE)

1. Find your skills directory: `~/.claude/skills/` (create it if it doesn't exist).
2. Copy the skills you want from this package's `skills/` folder into it:
   ```bash
   cp -R skills/lookahead-audit ~/.claude/skills/
   # or install the whole stack:
   cp -R skills/* ~/.claude/skills/
   ```
3. Restart Claude Code (or start a new session). The skills are now available.
4. Describe your task normally — e.g. *"audit my backtest in backtest.py for look-ahead bias."*
   Claude consults the matching skill automatically. To force one, name it:
   *"Use the lookahead-audit skill on backtest.py."*

## Claude.ai (web)

Upload a skill's `SKILL.md` (and any files in its `references/`) into a Project's knowledge, or paste
the `SKILL.md` contents into the conversation and ask Claude to follow it.

## Other agents (Codex, Gemini, etc.)

Because each skill is plain Markdown, it's portable: provide the `SKILL.md` as context/instructions to
any capable coding agent. The reference files load the same way.

## Verifying it works

Ask Claude: *"What skills do you have available?"* — the installed ones should be listed. Or run a
small task the skill targets and confirm it follows the skill's structure (e.g. the look-ahead audit
should return the report format defined in its `SKILL.md`).

## Tip — install only what you need

Skills consume a little context just by being available. Install the handful relevant to your current
work rather than all 25 at once; add more as your project grows.
