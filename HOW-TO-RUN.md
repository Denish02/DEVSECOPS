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

# Run it
docker run -d -p 8080:80 --name cloudmart-local cloudmart-app:local

# Confirm it's alive
curl http://localhost:8080/healthz.php
# {"status":"ok"}

# Open in a browser
#   http://localhost:8080/index.php
#   http://localhost:8080/about.php

# Stop and remove when done
docker stop cloudmart-local && docker rm cloudmart-local
```

If `curl` returns nothing, wait a few seconds — Apache takes a moment to start — and try again.

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
| `devsecops-pipeline.yml` | Any PR to `main`/`develop`, or a push to `main`/`develop` | Actions tab → select workflow → "Run workflow" (only push/PR events apply the full job graph) |
| `dast-scan.yml` | Automatically after `devsecops-pipeline.yml` finishes on `main` | Actions tab → "Run workflow" |
| `nightly-scan.yml` | Cron, 02:00 UTC daily | Actions tab → "Run workflow" |

### What actually happens on a PR vs. a push to `main`

- **Opening a PR**: `secrets-scan` → `sast-scan`/`sca-scan` → `build` → `container-scan`/`iac-scan`.
  Stops there — no staging deploy, no production deploy, no DAST. This is your fast feedback loop.
- **Pushing to `main`** (e.g. merging that PR): the same jobs run, then continue to
  `deploy-staging` → `dast-scan.yml` fires automatically → once you manually approve the
  `production` environment in the Actions UI → `deploy-production`.

### Where to see results

- **Security tab** (repo → Security → Code scanning alerts) — every SARIF upload (Trivy secrets/SCA/container/IaC, Semgrep) lands here, filterable by severity and tool.
- **Actions tab → the workflow run → Artifacts** — ZAP HTML/JSON reports, SBOMs (CycloneDX + SPDX), license report, compliance summary.
- **Actions tab → the workflow run → Summary** — the production deployment audit line (commit SHA, actor, timestamp) is written here by `deploy-production`.

---

## 4. How staging actually works here

The design doc originally assumed a real cloud staging environment reachable at a `STAGING_URL`.
This repo simplifies that so the whole pipeline runs on GitHub's free tier with no cloud account:

1. `deploy-staging` pushes the built image to `ghcr.io/<your-repo>:staging`.
2. `dast-scan.yml` pulls that image and runs it directly on the GitHub Actions runner
   (`docker run -d -p 8080:80 ...`), then points ZAP at `http://localhost:8080`.

Same DAST coverage, zero extra infrastructure. If you later stand up a real staging environment,
swap the "pull and run on the runner" steps in `dast-scan.yml`/`nightly-scan.yml` for a
`target: ${{ secrets.STAGING_URL }}` the way the original design doc describes.

---

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `deploy-staging`/`deploy-production` fails with a permissions error pushing to GHCR | Workflow permissions not set to read/write | Settings → Actions → General → Workflow permissions → "Read and write permissions" |
| `approval-gate` job runs without pausing | No required reviewer configured on the `production` environment | Settings → Environments → `production` → add a required reviewer |
| `dast-scan.yml` fails at "Run staging container" with an image-not-found error | `devsecops-pipeline.yml` hasn't successfully pushed a `:staging` tag yet (e.g. first run was only a PR, not a push to `main`) | Merge/push to `main` at least once first |
| Semgrep step fails immediately with an auth error | `SEMGREP_APP_TOKEN` secret is set but invalid | Remove the secret (it's optional) or fix its value |
| ZAP baseline scan reports a HIGH finding you believe is a false positive | — | Add a suppression line to `.github/zap/rules.tsv` (format: `<rule-id>\tIGNORE\t<rule-name>\t<reason>`) |
| Local `docker build` fails with a snapshot/extraction error | Transient BuildKit cache issue (seen occasionally on Docker Desktop for Windows) | Re-run `docker build`, or `docker builder prune -f` first |
