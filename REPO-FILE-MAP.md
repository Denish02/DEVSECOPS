# Repository File Map — CloudMart DevSecOps

Audit date: 2026-07-05 · Branch: `feature/seperated-the-cicd-flow`

**Verdict:** 18 files retained, 2 removed. `k8s/deployment.yaml` was deleted — never deployed by any workflow and internally stale from the pre-Flask (PHP) era (probes hit `/healthz.php` on port 80; the app serves `/healthz` on 8080). `terraform/main.tf` was also deleted — never applied by any workflow, described AWS ECR/S3 infrastructure that contradicted the live pipeline (which uses GHCR, not AWS). The Trivy IaC scan now covers only the `Dockerfile`.

---

## 1. File structure overview

```
.
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # CI: lint/test + security gates + image build
│   │   ├── cd.yml                  # CD: staging → DAST → approval → production
│   │   └── nightly-scan.yml        # Scheduled deep scans, SBOM, compliance
│   └── zap/
│       └── rules.tsv               # ZAP false-positive suppressions
├── src/                            # Flask sample app (the pipeline's subject)
│   ├── app/
│   │   ├── __init__.py             # App factory, routes, security headers
│   │   └── templates/
│   │       ├── index.html
│   │       └── about.html
│   ├── tests/test_app.py           # pytest suite run in CI
│   ├── wsgi.py                     # gunicorn entrypoint
│   ├── openapi.json                # API spec consumed by ZAP API scan
│   ├── requirements.txt            # flask, gunicorn (pinned)
│   ├── Dockerfile                  # python:3.13-slim, non-root, port 8080
│   └── .dockerignore
├── .gitignore
├── README.md                       # Overview ("what")
├── HOW-TO-RUN.md                   # Setup & run guide ("how")
├── PIPELINE-WALKTHROUGH.md         # Job-by-job trace ("in what order")
└── cloudmart-devsecops-technical-analysis.md  # Design rationale ("why")
```

---

## 2. File-by-file explanation

### CI/CD (`.github/`)

| File | Role |
|---|---|
| `workflows/ci.yml` | Runs on every PR/push to `main`. Seven jobs: `lint-test` (Ruff, Black, pytest), `secrets-scan` (Trivy, blocks on any secret), `sast-scan` (Semgrep, blocks on ERROR), `sca-scan` (Trivy vuln, blocks on CRITICAL), `build` (docker build, uploads image tarball artifact), `container-scan` (Trivy image, blocks on CRITICAL), `iac-scan` (Trivy config, warn-only — now scans just the Dockerfile). All scanners upload SARIF to the Security tab. |
| `workflows/cd.yml` | Triggered by `workflow_run` when CI succeeds on `main`. Chain: `deploy-staging` (push `:staging` tags to GHCR) → `smoke-staging` (`/healthz`) → `dast-staging` (ZAP baseline + API scan; blocks on HIGH) → `approval-gate` (`production` environment reviewer) → `deploy-production` (push `:prod-SHA` / `:latest`, audit log) → `smoke-production`. |
| `workflows/nightly-scan.yml` | Cron 02:00 UTC + manual. Report-only: full Trivy scan, SBOMs (CycloneDX + SPDX), license scan, full Semgrep, ZAP full active scan against the `:staging` image, then a compliance-summary artifact (365-day retention). Never blocks. |
| `zap/rules.tsv` | Suppresses two accepted ZAP informational findings (Cache-Control, timestamp disclosure) so DAST gates aren't polluted by known noise. |

### Application (`src/`)

| File | Role |
|---|---|
| `app/__init__.py` | Flask app factory. Routes: `/` (GET/POST greeting form), `/about`, `/healthz`, `/openapi.json`. Adds security headers (CSP, X-Frame-Options, nosniff) on every response; input truncated to 80 chars and auto-escaped by Jinja. |
| `app/templates/index.html` | Home page with the greeting form ZAP exercises. |
| `app/templates/about.html` | Static about page. |
| `tests/test_app.py` | 5 pytest tests: health endpoint, home page, XSS escaping, about page, security headers. Run by CI `lint-test`. |
| `wsgi.py` | Exposes `app = create_app()` for gunicorn (`wsgi:app`). |
| `openapi.json` | OpenAPI 3.0 spec of the four routes; served at `/openapi.json` and fed to ZAP's API scan in `cd.yml`. |
| `requirements.txt` | Pinned runtime deps (`flask==3.1.0`, `gunicorn==23.0.0`); also the SCA scan target and pip cache key. |
| `Dockerfile` | `python:3.13-slim`, installs deps, copies app, runs as non-root `appuser`, gunicorn on `0.0.0.0:8080`, HEALTHCHECK on `/healthz`. |
| `.dockerignore` | Keeps tests, docs, caches, and `.git` out of the image build context. |

### Documentation

| File | Role |
|---|---|
| `README.md` | Short overview: problem, tool stack, gate rules, layout, rollout plan, quick-start. |
| `HOW-TO-RUN.md` | Operational guide: local run, local scanner usage, one-time GitHub setup, troubleshooting. |
| `PIPELINE-WALKTHROUGH.md` | Traces one commit through every job in run order, with each gate's block/warn outcome. |
| `cloudmart-devsecops-technical-analysis.md` | Full design rationale: gap analysis, tool justification, gate decision framework, governance, KPIs, trade-offs. |

The four docs are complementary (what / how / in-what-order / why), cross-link each other, and contain no duplicated authority — each defers to the others for its slice. None are redundant.

### Repo hygiene

| File | Role |
|---|---|
| `.gitignore` | Excludes Python caches, venvs, and scanner outputs (`*.sarif`, ZAP reports, `*.tar`). |

---

## 3. Dependency map

```
                         ┌────────────────────────────────────────────┐
                         │              src/ application              │
                         │                                            │
 requirements.txt ──────►│ app/__init__.py ◄── templates/*.html       │
        │                │      ▲    │                                │
        │                │  wsgi.py  └──serves──► openapi.json        │
        │                │      ▲                                     │
        │                │ tests/test_app.py (imports create_app)     │
        │                └────────────────────────────────────────────┘
        │                        ▲
        └──────► Dockerfile ─────┘  (COPY app, wsgi.py, openapi.json;
                     ▲               .dockerignore trims the context)
                     │
              ci.yml build job ──► image artifact (cloudmart-app.tar)
                     ▲                        │
   ci.yml lint-test ─┤ runs tests/            │
   ci.yml sca-scan ──┤ scans requirements.txt │
   ci.yml iac-scan ──┤ scans Dockerfile       │
                     ▼                        ▼
              CI success on main ──workflow_run──► cd.yml
                                                    │ downloads image artifact
                                                    │ pushes :staging to GHCR
                                                    │ ZAP uses .github/zap/rules.tsv
                                                    │ ZAP API scan reads /openapi.json
                                                    ▼
                                          GHCR :staging image
                                                    ▲
                              nightly-scan.yml pulls it for ZAP full scan
```

Key interactions:

- **`ci.yml` → `cd.yml`**: coupled via `workflow_run` on the `CI` workflow name and the `cloudmart-app-image` artifact (downloaded by `run-id`). Renaming the CI workflow or the artifact breaks CD.
- **`cd.yml` → `nightly-scan.yml`**: nightly ZAP pulls the `:staging` tag that CD pushed to GHCR; before the first successful CD run, that job skips gracefully.
- **App contract**: `Dockerfile` HEALTHCHECK, both smoke tests, and ZAP readiness loops all depend on `GET /healthz` returning 200 on port 8080; ZAP's API scan depends on `/openapi.json` matching real routes.

---

## Removed in this audit

| File | Reason |
|---|---|
| `k8s/deployment.yaml` | Never deployed by any workflow, and internally stale from the pre-Flask (PHP) era — probes referenced `/healthz.php` on port 80 while the app serves `/healthz` on 8080. Recoverable from git history if a real cluster deployment is ever added. |
| `terraform/main.tf` | Never applied by any workflow (no `terraform init`/`apply` step exists). Described AWS ECR + S3 infrastructure that contradicted the live pipeline, which pushes images to GHCR, not ECR. Recoverable from git history if real AWS provisioning is ever added. |
