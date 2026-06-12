Security and secrets handling

1) If any credentials were accidentally committed, rotate them immediately (API keys, DB passwords, tokens).

2) To purge secrets from history locally, use git-filter-repo or the provided purge script (not included here). After rewriting history, force-push and inform collaborators to re-clone.

3) Never commit .env or secrets. This repo already includes .env in .gitignore.

4) Render deployment notes:
   - Configure all secrets in Render's Environment settings (GROQ_API_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, CLICKHOUSE_*).
   - Backend port: 8000. Root Dockerfile builds backend.

5) If you want assistance performing history purge from your machine, paste 'done' after running the purge script and I will validate the repo and help finish redeploy steps.