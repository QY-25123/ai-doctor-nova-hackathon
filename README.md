# AI Doctor

Monorepo: Next.js chat UI + FastAPI backend. Not for medical diagnosis; see [docs/safety.md](docs/safety.md).

## Structure

```
├── apps/
│   └── web/          # Next.js (App Router), TypeScript — chat UI at /chat
├── services/
│   └── api/          # FastAPI, Python — /health, /chat
├── docs/
├── docker-compose.yml
└── README.md
```

## Local run (no Docker)

### 1. API

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- Health: [http://localhost:8000/health](http://localhost:8000/health)
- Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Web

In a new terminal:

```bash
cd apps/web
npm install
npm run dev
```

- App: [http://localhost:3000](http://localhost:3000)
- Chat: [http://localhost:3000/chat](http://localhost:3000/chat)

The app calls the API at `http://localhost:8000` by default. Override with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Run with Docker

From the repo root:

```bash
docker compose up --build
```

- Web: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000](http://localhost:8000)

Stop: `docker compose down`.

**Reproducible web builds:** For reproducible Docker builds of the web app, generate and commit `package-lock.json`: run `npm install` in `apps/web` once, then commit the lockfile. The web Dockerfile uses `npm install`; with a lockfile present, installs will match across builds.

## Tech

- **Web:** Next.js 14 (App Router), TypeScript, React 18
- **API:** FastAPI, Python 3.12, Uvicorn

---

## Production deployment (hackathon‑simple)

Two minimal options. Use **Secrets Manager** for any secrets (e.g. `DATABASE_URL`); reference by ARN in the service config.

### Required env vars

| Var | Where | Purpose |
|-----|--------|---------|
| `NEXT_PUBLIC_API_URL` | Web (build-time) | Full API base URL the browser will call (e.g. `https://api.example.com`) |
| `BEDROCK_MODEL_ID` | API | LLM model (default: `us.amazon.nova-lite-v1:0`) |
| `BEDROCK_EMBED_MODEL_ID` | API | Embeddings model (default: `amazon.titan-embed-text-v2:0`) |
| `DATABASE_URL` | API | SQLite path or RDS URI (e.g. `sqlite:///./data/ai_doctor.db` or `postgresql://...`) |

Optional: store `DATABASE_URL` (or other secrets) in **AWS Secrets Manager** and inject via task definition / App Runner config (see below).

### IAM: Bedrock Runtime

The API task/instance needs permission to call Bedrock. Attach a policy like:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
```

(Or narrow `Resource` to specific model ARNs if you prefer.)

### Secrets Manager (optional)

1. Create a secret (e.g. `ai-doctor/prod`) with key/value or JSON: e.g. `{"DATABASE_URL":"..."}`.
2. Give the API role permission: `secretsmanager:GetSecretValue` on that secret’s ARN.
3. In the deployment config, either:
   - **App Runner:** Add secret from Secrets Manager; map to env var `DATABASE_URL`.
   - **ECS:** In the task definition, use `secrets` to pull the secret value into `DATABASE_URL`.

---

### Option A: App Runner (API) + Vercel (Web)

**1. API — AWS App Runner**

- **Source:** ECR image built from `services/api/Dockerfile` (build and push from repo root: `docker build -t <ecr-uri> ./services/api`, then push).
- **Service settings:** CPU/memory as needed; port **8000**.
- **Env vars:** Set `BEDROCK_MODEL_ID`, `BEDROCK_EMBED_MODEL_ID`; set `DATABASE_URL` or attach from Secrets Manager (see above).
- **IAM:** Use a role that has the Bedrock Runtime policy and (if used) Secrets Manager access. Attach this role to the App Runner service.
- **Health check:** Path `/health`.

**2. Web — Vercel**

- **Project:** Import repo; root directory leave as repo root; set **Framework Preset** to Next.js.
- **Build:** Build command `npm run build` (or `cd apps/web && npm run build` if root build not configured). Set **Root Directory** to `apps/web` so `package.json` and `next.config.js` are there.
- **Env var:** Add `NEXT_PUBLIC_API_URL` = your App Runner URL (e.g. `https://xxx.us-east-1.awsapprunner.com`). Redeploy after adding so the client bundle picks it up.

**3. CORS**

- API already allows `allow_origins=["*"]`. For production you can restrict to your Vercel domain.

---

### Option B: ECS Fargate (API) + S3/CloudFront (Web)

**1. API — ECS Fargate**

- **Image:** Build and push `services/api/Dockerfile` to ECR.
- **Task definition:** 
  - Container port **8000**; same for host/mapping.
  - **Env:** `BEDROCK_MODEL_ID`, `BEDROCK_EMBED_MODEL_ID`. For `DATABASE_URL`, use **Secrets** and reference your Secrets Manager secret (key → env name `DATABASE_URL`).
  - **Task role:** Attach the same Bedrock + (optional) Secrets Manager policy so the task can call Bedrock and read the secret.
- **Service:** Fargate; desired count 1; place behind an **ALB** (target group port 8000; health check `/health`).
- **Security group:** Allow inbound 8000 from ALB; outbound for Bedrock (HTTPS) and RDS if used.

**2. Web — S3 + CloudFront**

- **Build:** From repo root, `cd apps/web && npm run build`. Use **output: "standalone"** (already in `next.config.js`). For static export instead, use `next export` and upload `out/` to S3; otherwise run the Node server elsewhere or use a different hosting pattern.  
  **Hackathon‑simple:** Build the Next app, then either:
  - **Static:** If you switch to static export, upload `out/` to an S3 bucket, enable static hosting, and use CloudFront in front of S3.
  - **Or** run the Next server in a second Fargate service and put both API and Web behind the same ALB (different paths) or two CloudFront origins.
- **Env:** Build with `NEXT_PUBLIC_API_URL` set to your API base URL (ALB or CloudFront to API).
- **CloudFront:** Origin = S3 (or Fargate for the Next server); HTTPS; optionally attach a custom domain.

**3. Summary**

- API: ECS Fargate task with Bedrock + Secrets Manager (for `DATABASE_URL`) IAM; env/secrets in task def; ALB health check `/health`.
- Web: S3 + CloudFront (static) or second Fargate service; `NEXT_PUBLIC_API_URL` points at the API.

---

### Checklist

- [ ] API env: `BEDROCK_MODEL_ID`, `BEDROCK_EMBED_MODEL_ID`, `DATABASE_URL` (or from Secrets Manager).
- [ ] API IAM: Bedrock `InvokeModel` (+ optional Secrets Manager `GetSecretValue`).
- [ ] Web build env: `NEXT_PUBLIC_API_URL` = public API URL.
- [ ] Health: API exposes `/health`; use it for load balancer / App Runner health checks.
# ai-doctor-nova-hackathon
