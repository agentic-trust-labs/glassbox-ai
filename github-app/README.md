# GlassBox Agent - GitHub App

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/agentic-trust-labs/glassbox-ai)

## How it works

```
User installs app          GitHub sends webhook       Server runs agent
─────────────────          ────────────────────       ─────────────────
github.com/apps/     →     POST /webhook with    →    Clone repo
glassbox-agent             issue/comment data          Analyze issue
Click "Install"            (automatic)                 Generate fix
Select repos                                           Run tests
                                                       Create PR
```

One-click install for users. No workflow files, no configuration, no secrets on their end.

## Architecture

| Component | What | Status |
|-----------|------|--------|
| **GitHub App** | Registered at `github.com/apps/glassbox-agent` (ID: `2868564`) | ✅ Live |
| **Machine User** | `@glassbox-agent` account for @mention autocomplete | ✅ Live |
| **Webhook Server** | FastAPI server - receives events, authenticates, runs agent | ✅ Code ready |
| **Agent Pipeline** | Manager → JuniorDev → Tester → PR | ✅ Working |

### Why a machine user too?

GitHub Apps cannot appear in @mention autocomplete (platform limitation). Every bot with working autocomplete uses a machine user: `@claude`, `@renovate-bot`, `@codecov-commenter`.

## Deploy the webhook server

### One-click: Render (free tier)

1. Click the **Deploy to Render** button above
2. Sign in with GitHub
3. Set these 4 environment variables:

| Variable | Where to get it |
|----------|----------------|
| `GITHUB_APP_ID` | Already in repo secrets (`2868564`) |
| `GITHUB_APP_PRIVATE_KEY` | Already in repo secrets (PEM content, replace newlines with `\n`) |
| `GITHUB_WEBHOOK_SECRET` | Generate: `openssl rand -hex 20` |
| `OPENAI_API_KEY` | Your OpenAI key |

4. Deploy - note the URL (e.g. `https://glassbox-agent.onrender.com`)
5. Update the GitHub App webhook URL:
   - Go to: `github.com/organizations/agentic-trust-labs/settings/apps/glassbox-agent`
   - Set Webhook URL to: `https://YOUR_URL/webhook`
   - Set Webhook secret to the same secret from step 3
   - Check "Active"

### Alternative: Fly.io

```bash
fly launch --dockerfile github-app/Dockerfile
fly secrets set GITHUB_APP_ID=... GITHUB_APP_PRIVATE_KEY=... GITHUB_WEBHOOK_SECRET=... OPENAI_API_KEY=...
```

## Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI webhook server - receives events, runs agent pipeline |
| `auth.py` | GitHub App JWT auth - generates installation access tokens |
| `Dockerfile` | Container image with agent code baked in |
| `requirements.txt` | Server dependencies (FastAPI, PyJWT, httpx) |
| `railway.json` | Railway deployment config |
| `manifest.json` | GitHub App definition (permissions, events) |
| `setup.py` | One-time app creation via manifest flow |

## For end users (summit attendees)

1. Go to **github.com/apps/glassbox-agent**
2. Click **Install**
3. Select your repos
4. Create an issue describing a bug, add label `glassbox-agent`
5. Agent responds, analyzes, fixes, creates PR

No secrets. No workflow files. No configuration.

## Secrets (already configured)

| Secret | Source | Purpose |
|--------|--------|---------|
| `APP_ID` | GitHub App | JWT authentication |
| `APP_PRIVATE_KEY` | GitHub App | JWT signing |
| `BOT_PAT` | Machine user | GitHub Actions (internal repo only) |
| `OPENAI_API_KEY` | OpenAI | LLM calls |

## Security

- All secrets stored as GitHub repo secrets, never in code
- `.gitignore` prevents committing `*.pem` files
- Machine user has push (not admin) access
- GitHub App has minimum required permissions: `issues:write`, `pull_requests:write`, `contents:write`, `metadata:read`
- Webhook signature verification (HMAC SHA-256)
