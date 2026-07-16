# Deploy

Free, GitHub-integrated, works from any browser (Mac + Windows).

## 1. Push to a PERSONAL GitHub repo
Vercel's free Hobby plan can't connect org-owned repos, so use a personal repo.

```bash
gh repo create momentum-swing-dashboard --private --source=. --push
# or create it on github.com and: git remote add origin <url> && git push -u origin main
```

## 2. API keys → GitHub Actions secrets
The engine runs in GitHub Actions (not Vercel). Add free keys as repo secrets:

```bash
gh secret set POLYGON_API_KEY   # https://polygon.io  (free "Massive" tier)
gh secret set FINNHUB_API_KEY   # https://finnhub.io  (free tier)
# optional:
gh secret set TIINGO_API_KEY
# optional repo VARIABLE to cap the universe on the free rate limit while testing:
gh variable set CONTEXT_UNIVERSE_LIMIT --body 300
```

The scheduled workflow (`.github/workflows/engine.yml`) runs the scan + backtest
after the US close and midday, then commits refreshed JSON to
`web/public/data/`, which triggers a Vercel redeploy.

> Tip: make the repo **public** for unlimited Actions minutes (private = 2,000
> min/mo, still plenty). Public means your watchlist is visible — your call.

## 3. Frontend → Vercel (free)
1. Sign up at vercel.com **with your GitHub account**.
2. "Add New Project" → import the repo.
3. **Set the Root Directory to `web/`.** (Framework auto-detects as Next.js.)
4. No environment variables are needed — the frontend only reads committed JSON.
5. Deploy. Every future data commit auto-redeploys.

## Local development
```bash
# engine (Python)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local   # add POLYGON_API_KEY / FINNHUB_API_KEY (optional; synthetic without)
python -m engine && python -m engine.backtest

# web (Next.js) — needs Node 20+ (nvm recommended, no sudo):
#   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
#   nvm install 20
cd web && npm install && npm run dev   # http://localhost:3000
```
