# Workout Tracker

Self-hosted workout tracking app that scrapes daily workouts from [Full Range PVD](https://www.fullrangepvd.com/blog) and lets you log results, track PRs, and review history.

## Architecture

- **Backend:** FastAPI + PostgreSQL + Alembic
- **Frontend:** React + TypeScript + Tailwind CSS (Vite)
- **Auth:** Authentik OIDC
- **Parsing:** 3-tier pipeline (Ollama -> Claude API -> Regex)
- **Deployment:** Docker Compose behind Traefik

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 2. Start services

```bash
docker compose up -d
```

The backend runs migrations automatically on startup. The frontend is available on port 80 (via Nginx proxy to the backend API).

### 3. Seed first user (development)

```bash
docker compose exec backend python seed.py
```

## Authentik OIDC Setup

### Step 1: Create a Provider in Authentik

1. Log in to your Authentik admin panel
2. Go to **Applications > Providers**
3. Click **Create** and select **OAuth2/OpenID Provider**
4. Configure:
   - **Name:** `Workout Tracker`
   - **Authorization flow:** Select your default authorization flow
   - **Client type:** Confidential
   - **Client ID:** Copy this value for `OIDC_CLIENT_ID`
   - **Client Secret:** Copy this value for `OIDC_CLIENT_SECRET`
   - **Redirect URIs:** `https://workout.yourdomain.com/auth/callback`
   - **Scopes:** `openid`, `profile`, `email`
   - **Subject mode:** Based on the User's hashed ID
   - **Signing Key:** Select your default signing key (RS256)
5. Save

### Step 2: Create an Application

1. Go to **Applications > Applications**
2. Click **Create**
3. Configure:
   - **Name:** `Workout Tracker`
   - **Slug:** `workout-tracker`
   - **Provider:** Select the provider you just created
   - **Launch URL:** `https://workout.yourdomain.com`
4. Save

### Step 3: Set environment variables

```env
OIDC_ISSUER_URL=https://auth.yourdomain.com/application/o/workout-tracker/
OIDC_CLIENT_ID=<from step 1>
OIDC_CLIENT_SECRET=<from step 1>
OIDC_REDIRECT_URI=https://workout.yourdomain.com/auth/callback
```

### Step 4: Assign users

In Authentik, go to the application's **Policy/Group bindings** and add the users or groups that should have access.

## Traefik Integration

The `docker-compose.yml` includes commented-out Traefik labels. Uncomment and adjust to match your setup:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.workout.rule=Host(`workout.yourdomain.com`)"
  - "traefik.http.routers.workout.entrypoints=websecure"
  - "traefik.http.services.workout.loadbalancer.server.port=80"
```

## Ollama Setup

The scraper uses Ollama as its primary LLM parser. Since Ollama runs on a separate machine:

1. Ensure Ollama is running and accessible from your Docker network
2. Set `OLLAMA_URL` in `.env` to the Ollama server's address (e.g. `http://192.168.1.100:11434`)
3. Pull the model: `ollama pull mistral:7b` (on the Ollama machine)

If Ollama is unreachable, the scraper falls back to Claude API (requires `ANTHROPIC_API_KEY`), then to regex-based parsing.

## Scraper

The scraper runs daily on a cron schedule (default 5am, configurable via `SCRAPER_CRON`).

### Manual trigger

```bash
# Scrape today's workout
curl -X POST https://workout.yourdomain.com/api/scraper/trigger \
  -H "Authorization: Bearer <token>"

# Scrape a specific date
curl -X POST "https://workout.yourdomain.com/api/scraper/trigger?date=2025-01-15" \
  -H "Authorization: Bearer <token>"

# Re-parse without re-fetching
curl -X POST https://workout.yourdomain.com/api/scraper/reparse/1 \
  -H "Authorization: Bearer <token>"
```

### Parse confidence

- Workouts parsed with confidence < 0.75 are flagged for review
- Flagged workouts trigger a webhook alert if `ALERT_WEBHOOK_URL` is set
- Review flagged workouts at **GET /api/admin/flagged**

## API Documentation

Auto-generated docs available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run tests

```bash
cd backend
pytest tests/ -v
```

## Project Structure

```
workout-tracker/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── scraper/      # Scraper + LLM parsing pipeline
│   │   ├── auth/         # OIDC validation
│   │   └── core/         # Config, DB session, cache
│   ├── alembic/          # Database migrations
│   ├── tests/
│   ├── seed.py           # First user seed script
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Route pages
│   │   ├── hooks/        # React hooks
│   │   └── types/        # TypeScript types
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```
