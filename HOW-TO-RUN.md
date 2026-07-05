# How to Run the CloudMart DevSecOps Pipeline

This is the step-by-step guide for actually running what's in this repo — locally, and as GitHub
Actions. For *why* the pipeline is built this way, see
[`cloudmart-devsecops-technical-analysis.md`](./cloudmart-devsecops-technical-analysis.md).
For the short overview, see [`README.md`](./README.md).

---

## 1. Run the app locally (no GitHub needed)

You need Docker Desktop (or any Docker engine) installed and running.

```bash
# Build the image
docker build -t cloudmart-app:local ./src

# Run it (gunicorn serves the Flask app on 8080 inside the container)
docker run -d -p 8080:8080 --name cloudmart-local cloudmart-app:local

# Confirm it's alive
curl http://localhost:8080/healthz
# {"status":"ok"}

# Open in a browser
#   http://localhost:8080/
#   http://localhost:8080/about

# Stop and remove when done
docker stop cloudmart-local && docker rm cloudmart-local
```

If `curl` returns nothing, wait a few seconds — gunicorn takes a moment to start — and try again.

### Try the scanners locally too (optional)

You don't need GitHub Actions to see what each tool finds. All three run as standalone CLIs / Docker images:

```bash
# Trivy — secrets, dependencies, container, IaC (needs Trivy installed, or use the Docker image)
docker run --rm -v "$(pwd):/repo" aquasec/trivy fs --scanners secret,vuln /repo
docker run --rm cloudmart-app:local # (build first, then scan the image by name/tag)
docker run --rm -v "$(pwd):/repo" aquasec/trivy image cloudmart-app:local
docker run --rm -v "$(pwd):/repo" aquasec/trivy config /repo

# Semgrep — SAST
docker run --rm -v "$(pwd)/src:/src" semgrep/semgrep semgrep scan --config=auto /src

# OWASP ZAP — DAST (target must already be running, e.g. from step above)
docker run --rm --network host zaproxy/zap-stable zap-baseline.py -t http://localhost:8080
```

---

## 2. One-time GitHub repository setup

Do this once, before the first push that should run the full pipeline.

### 2.1 Enable Actions and package publishing

1. **Settings → Actions → General → Actions permissions** → allow all actions.
2. **Settings → Actions → General → Workflow permissions** → select **"Read and write
   permissions"**. This lets the built-in `GITHUB_TOKEN` push images to GitHub Container Registry
   (GHCR) without any extra secret.

### 2.2 Create the two GitHub Environments

**Settings → Environments → New environment**

| Environment | Protection rules |
|---|---|
| `staging` | None needed |
| `production` | Add **required reviewers** — at least one person (this is your stand-in for "Security Lead / Release Manager") |

Without the `production` required-reviewer rule, the approval-gate job in the pipeline will
auto-pass with nobody actually reviewing anything.

### 2.3 (Optional) Secrets

| Secret | Needed? | Purpose |
|---|---|---|
| `SEMGREP_APP_TOKEN` | No | Only needed if you want Semgrep results mirrored to Semgrep Cloud's dashboard. The pipeline works fully without it (free OSS engine, results still go to the GitHub Security tab). |

No `STAGING_URL` secret is needed — see [§4](#4-how-staging-actually-works-here) for why.

---

## 3. Triggering each workflow

| Workflow | Fires on | Or trigger manually |
|---|---|---|
| `ci.yml` | Any PR to `main`, or a push to `main` | Not exposed as `workflow_dispatch` — push/PR only |
| `cd.yml` | Automatically after `ci.yml` **succeeds on `main`** (`workflow_run`) | — (driven by CI completion) |
| `nightly-scan.yml` | Cron, 02:00 Malaysia Time / 18:00 UTC daily | Actions tab → "Run workflow" |

For a job-by-job trace of what each step does and what blocks it, see
[`PIPELINE-WALKTHROUGH.md`](./PIPELINE-WALKTHROUGH.md).

### What actually happens on a PR vs. a push to `main`

- **Opening a PR**: `ci.yml` runs `lint-test` + `secrets-scan` + `sast-scan` + `sca-scan` in
  parallel → `build` → `container-scan`/`iac-scan`. Stops there — no deploy, no DAST. This is your
  fast feedback loop.
- **Pushing to `main`** (e.g. merging that PR): the same CI jobs run, and on success `cd.yml` fires
  automatically: `deploy-staging` → `smoke-staging` → `dast-staging` (ZAP) → `approval-gate` (you
  click Approve on the `production` environment) → `deploy-production` → `smoke-production`.

### Where to see results

- **Security tab** (repo → Security → Code scanning alerts) — every SARIF upload (Trivy secrets/SCA/container/IaC, Semgrep) lands here, filterable by severity and tool.
- **Actions tab → the workflow run → Artifacts** — ZAP HTML/JSON reports, SBOMs (CycloneDX + SPDX), license report, compliance summary.
- **Actions tab → the workflow run → Summary** — the production deployment audit line (commit SHA, actor, timestamp) is written here by `deploy-production`.

---

## 4. How staging actually works here

The design doc originally assumed a real cloud staging environment reachable at a `STAGING_URL`.
This repo simplifies that so the whole pipeline runs on GitHub's free tier with no cloud account:

1. `deploy-staging` (in `cd.yml`) pushes the built image to `ghcr.io/<your-repo>:staging`.
2. The `dast-staging` job (also in `cd.yml`) pulls that image and runs it directly on the GitHub
   Actions runner (`docker run -d -p 8080:8080 ...`), then points ZAP at `http://localhost:8080`.

Same DAST coverage, zero extra infrastructure. If you later stand up a real staging environment,
swap the "pull and run on the runner" steps in `cd.yml`/`nightly-scan.yml` for a
`target: ${{ secrets.STAGING_URL }}` the way the original design doc describes.

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `deploy-staging`/`deploy-production` fails with a permissions error pushing to GHCR | Workflow permissions not set to read/write | Settings → Actions → General → Workflow permissions → "Read and write permissions" |
| `approval-gate` job runs without pausing | No required reviewer configured on the `production` environment | Settings → Environments → `production` → add a required reviewer |
| `cd.yml` doesn't run at all after a push | `cd.yml` only fires when `ci.yml` **concludes `success` on `main`** — a failed CI gate (or a PR-only run) never triggers CD | Fix the failing CI gate, or push to `main` (not just open a PR) |
| `nightly-scan.yml`'s ZAP job logs "No staging image yet, skipping" | No `:staging` tag has been pushed to GHCR yet (CD hasn't run a successful `deploy-staging`) | Merge/push to `main` so CI→CD runs at least once first |
| Semgrep step fails immediately with an auth error | `SEMGREP_APP_TOKEN` secret is set but invalid | Remove the secret (it's optional) or fix its value |
| ZAP baseline scan reports a HIGH finding you believe is a false positive | — | Add a suppression line to `.github/zap/rules.tsv` (format: `<rule-id>\tIGNORE\t<rule-name>\t<reason>`) |
| Local `docker build` fails with a snapshot/extraction error | Transient BuildKit cache issue (seen occasionally on Docker Desktop for Windows) | Re-run `docker build`, or `docker builder prune -f` first |
