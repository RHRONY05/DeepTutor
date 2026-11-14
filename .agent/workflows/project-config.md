---
description: Set up the builder for this fork once (servers, permission grants, tools), then report what Rony must still do
---

Rony runs this **once, before the first goal**, so the build is never stopped by a disabled server,
a permission prompt or a localhost prompt. It doesn't build anything. Turning servers off later is Rony's call.

## What this project needs
| Kind | Needed | Used for |
|---|---|---|
| MCP server | `chrome-devtools` | Checking the V1/V5 UI ACs in a real browser (optional: the agent's own browser works too) |
| Execute/read URL | `localhost`, `127.0.0.1`, `[::1]` | DeepTutor dev server (backend + web) |
| Read URL | `github.com`, `raw.githubusercontent.com`, `pypi.org`, `antigravity.google`, `agentclientprotocol.com`, `code.claude.com` | Reading DeepTutor source/issues, package pages, Antigravity ACP docs, the ACP spec, Claude Agent SDK docs |
| CLI | `python` (3.11–3.14), `.venv\Scripts\python`, `pip`, `pytest`, `ruff`, `node` ≥ 20, `npm`, `git`, `agy`, `claude`, `deeptutor` | Everything |
| Secret (human) | none required. Optional: a free Gemini AI Studio key, pasted in the DeepTutor UI (never in files) | V5 AC 6 (embeddings) |

No Supabase, Vercel or GitHub access is needed. **Do not enable or grant GitHub push**: this fork is never pushed by the builder.

## Steps
1. Find out which builder you are and use its section below. Never touch another builder's files.
2. Enable `chrome-devtools` if it exists. If it's missing, add it only if its config needs no secret (`npx chrome-devtools-mcp@latest`), otherwise list it under "Needs Rony".
3. Write permission grants **in this project's config only**: the server wildcard, the URLs, and the CLIs above. Never edit global grants.
4. Check for real: `chrome-devtools` → `list_pages`. Run `python --version`, `node -v`, `git --version`, `agy --version`, `claude --version`. Don't run any `agy` prompt here.
5. Write a **Builder setup** table into `.agent/PROGRESS.md` (under "Environment facts"): item · ✅/❌ · what you did / what Rony must do · date + builder. Add each ❌ to "Human steps".
6. Stop and report: ✅ done, ❌ needs Rony (exact step each). Then: "When the ❌ list is empty, paste the goal command."

## Antigravity
- Servers: `agy mcp list`, then `agy mcp enable chrome-devtools` (only flip `disabled` for that entry in `~/.gemini/config/mcp_config.json`, don't change others).
- Grants: the project file in `~/.gemini/config/projects/` whose content points at `D:\Projects\DeepTutor` (if none does, that's a ❌: ask Rony to open the folder in Antigravity once). Add to `permissionGrants.permissionGrants.allow`, keeping what's there: `"mcp(chrome-devtools/*)"`, `"execute_url(<host>)"` + `"read_url(<host>)"` for each localhost host, `"read_url(<host>)"` for each Read URL host.
- Never edit `globalPermissionGrants` in `~/.gemini/config/config.json`.

## Claude Code
- Grants: `.claude/settings.local.json` in this project (git-ignored), `permissions.allow`: `mcp__chrome-devtools`, `WebFetch(domain:<host>)` for each Read URL host, `Bash(python *)`, `Bash(.venv/Scripts/python *)`, `Bash(pip *)`, `Bash(pytest *)`, `Bash(ruff *)`, `Bash(npm *)`, `Bash(node *)`, `Bash(git *)`, `Bash(agy *)`, `Bash(claude --version)`, `Bash(deeptutor *)`.
- Never edit `~/.claude/settings.json`.

## Codex
- Say in the report which approval mode the build needs (no prompts for shell and localhost). Don't change the user-wide config.

## Turn off (only when Rony asks)
Disable the servers he names and leave the grants unless he asks to remove them too. Update the Builder setup table.
