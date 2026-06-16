# Devcontainer

An isolated Linux container for working on this project. Because it is sandboxed
from your host machine, you can run Claude Code without permission prompts.
Inside the container `claude` is aliased to:

```bash
claude --dangerously-skip-permissions --model opus
```

So just running `claude` skips permissions and uses Opus by default. Anything
Claude does stays inside the container, so a bad command can't touch your real
files.

## What's inside

- Debian bookworm with the `vscode` user
- `uv` for Python (the venv is created by `uv sync` on first start)
- Node LTS plus the `@anthropic-ai/claude-code` CLI
- Standard CLI tools: `git` (from the base image), `gh`, `jq`, `ripgrep`
- The system Chromium libraries that `kaleido` needs to render the PDF report

## Using it

Open the project in VS Code and run "Dev Containers: Reopen in Container", or use
the Dev Containers CLI. After the build, `uv sync` runs automatically.

Start the app:

```bash
uv run python app.py
```

Port 8050 is forwarded, so the dashboard opens on your host browser.

## Auth

The container is fully isolated from your host. Claude authenticates through
Microsoft Foundry using three variables read from your host environment and
passed through (see `containerEnv` in `devcontainer.json`):

```bash
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_API_KEY=...
export ANTHROPIC_FOUNDRY_RESOURCE=...
export GITHUB_PAT=...   # passed through as GH_TOKEN so gh is authenticated
```

Make sure these are set on your host before launching.

Your credentials, history, hooks, and settings are NOT mounted, so a runaway
agent can't read your secrets or rewrite hooks that would later run on your host.

## Your working style

So Claude follows your usual conventions, your global instruction files are
mounted read-only into `/home/vscode/.claude/`:

- `CLAUDE.md` (and its `@`-imports `RTK.md`, `github-issue-workflow.md`)
- `rules/` (e.g. `r-package.md`)

Read-only means Claude can read them but can't rewrite them, and none of them
contain secrets. Edit them on your host and the changes show up on the next
container start. Note that tools referenced in there which aren't installed in
the container (rtk, the Obsidian REST API) simply won't be available here.
