# CD-3C — BTC shared self-hosted runner artifact workflow

**Repository:** AI20K-Build-Phase-Cohort-3/P-217 (CHAT-03)
**Phase date:** 2026-08-27, Asia/Bangkok
**Scope:** focused production-artifact workflow adaptation for the BTC shared self-hosted runner path. No deployment channel was added.

## Verdict

# PASS_STATIC_PR_OPEN

BTC/Admin has confirmed that GitHub-hosted Actions jobs may be blocked by the organization billing/spending limit and has designated plain self-hosted as the official shared-runner workaround. This phase adapts only the exact-SHA Gate and immutable GHCR artifact Build jobs to that runner path.

The implementation is isolated on an unmerged PR. No workflow was dispatched in CD-3C, so BTC-runner availability, GHCR authorization, registry push/reuse, digests, and OCI metadata remain runtime-unproven.

## Reason for the architecture change

The controlled CD-3B2 run 33072012646 was rejected before Gate execution because GitHub reported an account billing/spending-limit problem. Its Gate job had no executed steps and the Build job was skipped; no GHCR operation occurred.

BTC/Admin subsequently confirmed that shared self-hosted runners are the official FIFO path for all teams. The prior requirement for production artifact Gate/Build jobs to use GitHub-hosted ubuntu-latest is therefore superseded only for those artifact jobs. Production deployment remains explicitly outside this workflow and this phase.

## Exact changed files

| File | Change |
| --- | --- |
| .github/workflows/deploy-production.yml | Gate and Build/reuse now run on exactly self-hosted; adds fail-fast runner prerequisite checks and explicit shared-runner Docker hygiene. |
| tests/test_scripts/test_deploy_workflow_static.py | New narrow static contract test for runner selection, prerequisite checks, credential handling, exact-SHA/GHCR invariants, deployment exclusion, and ci.yml preservation. |
| MD/CI-CD/CD_PHASE_3C_BTC_RUNNER_REPORT.md | This phase report. |

No application source, Dockerfile, Compose file, Caddyfile, runtime environment file, or existing CI workflow changed.

## Runner configuration

| Job | Before | After |
| --- | --- | --- |
| gate | ubuntu-latest | self-hosted |
| build-or-reuse | ubuntu-latest | self-hosted |

The runner value is exactly plain self-hosted. No unapproved labels, runner-group names, or own-infrastructure assumption were added. Existing .github/workflows/ci.yml is unchanged.

## Shared-runner hardening and residual risk

### Explicit workflow protections

- Gate checks for bash, git, gh, and jq before checkout/gating. Missing tools fail normally and clearly; the workflow does not install them.
- Build checks Docker daemon access and Docker Buildx before registry authentication. A missing Docker/Buildx prerequisite fails the job; no sudo, apt, yum, dnf, apk, or host installation step exists.
- GHCR login uses only github.actor and the job-scoped GITHUB_TOKEN. No PAT or repository Secret is introduced.
- docker/login-action is configured with logout: true, so its GHCR credential is removed by its job cleanup.
- docker/setup-buildx-action has install: false, cleanup: true, and keep-state: false. It may create an ephemeral Buildx builder for the job but is configured not to retain BuildKit state after cleanup.
- The workflow has no custom temporary Docker configuration, no token echo, and no generated secret file.
- The static test rejects SSH, SCP, deployment helper, production environment-path, Alembic, sudo, package-manager installation, and runtime-secret references.

### Residual risk

BTC owns and operates the physical shared runner. This repository cannot prove its host-level isolation, disk cleanup, or cross-job boundary. Checkout content, public frontend build values, and Buildx/GitHub cache behavior must therefore be treated as running on BTC-managed shared infrastructure.

This workflow intentionally supplies no production SSH key, VPS runtime environment, database credential, JWT secret, application-provider key, SMTP credential, Supabase service-role credential, or production sudo/root credential. It does not add a production SSH/VPS deployment job.

## Preserved production-artifact safety contract

The runner adaptation preserves all reviewed controls:

- workflow_dispatch with required release_sha;
- exact 40-character SHA validation and lowercase normalization;
- commit existence plus develop_v2 ancestry validation;
- exact successful ci.yml push-run/head-SHA equality gate;
- Build checkout from the validated Gate output, not workflow-definition SHA;
- production concurrency group linguaflow-production with cancellation disabled;
- immutable full-SHA backend/frontend GHCR identities and no latest tag;
- partial-image-state failure without overwrite/delete;
- OCI revision/source labels and digest evidence for build and reuse paths;
- distinct backend and frontend GitHub Actions cache scopes;
- required repository Actions Variables for both public frontend build values;
- least-privilege Gate and Build permissions;
- no application runtime secret reference;
- no SSH, VPS, Compose, migration, database, or production action.

## Docker/Buildx compatibility decision

The workflow continues to use standard Docker actions already reviewed for the artifact job:

- docker/login-action@v3;
- docker/setup-buildx-action@v3;
- docker/build-push-action@v6.

These actions are runner-agnostic provided the BTC Linux runner exposes a usable Docker daemon and Buildx. The workflow now verifies required Gate utilities, Docker, and Buildx before using them. It does not attempt global Docker installation or privileged host mutation if the runner lacks a prerequisite.

The workflow uses a path checkout so the build context remains the validated release SHA. Standard Buildx setup is required for the existing exact-image inspection, push, and gha cache contract; cleanup is explicitly enabled for the persistent shared-runner model.

## Static validation

| Check | Command/result |
| --- | --- |
| BTC runner workflow contract | py -3 tests/test_scripts/test_deploy_workflow_static.py → BTC shared-runner workflow static validation passed. |
| Workflow/test whitespace | git diff --check and no-index check for the added test → pass. |
| Existing CI preservation | git diff --exit-code origin/main -- .github/workflows/ci.yml → exit 0. |
| Existing CI blob | 911e4040c837dfbd359db421b61c622f1e4e7d63, unchanged from origin/main. |
| Existing deployment-tooling harness | Absent from the clean current origin/main baseline; no unrelated uncommitted develop_v2 harness was copied into this branch. |

The static test requires both artifact jobs to use exactly self-hosted and rejects ubuntu-latest. It additionally tests all preserved exact-SHA, GHCR, OCI, concurrency, Variable, secret-boundary, and deployment-exclusion invariants described above.

## Git integration

| Item | Value |
| --- | --- |
| Base | origin/main at 25780f82ede5646b62b5d0e67fbca11565af0038 |
| Branch | chore/cd-btc-self-hosted-runner |
| Artifact runner commits | aab8fc07691192d56ab83b65217b2a53833313e4; 8d8f997 |
| Pull request | [PR #55 — ci(cd): run production image build on BTC self-hosted runner](https://github.com/AI20K-Build-Phase-Cohort-3/P-217/pull/55) |
| PR state at creation | OPEN; not merged |

Only the dedicated branch was pushed. No direct push to main, develop_v2, or develop occurred. No merge was performed.

## Required prerequisites for a later CD-3B2 retry

1. PR #55 must be reviewed and merged by an authorized maintainer; CD-3C does not merge it.
2. BTC must make a FIFO shared self-hosted runner available to the job. It must provide bash, git, gh, jq, Docker daemon access, and Docker Buildx; the workflow fails safely if any are absent.
3. The two repository Actions Variables must remain nonempty:
   NEXT_PUBLIC_API_URL and NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID.
4. The job-scoped GITHUB_TOKEN must be permitted to create/access repository-linked private GHCR packages with packages: write. This is still unproven until a controlled workflow run.
5. Start one new CD-3B2 preflight/run after merge and observe Gate, GHCR login, image build/reuse, immutable digests, and OCI revision evidence. If the BTC queue is delayed, wait or record the queue state; do not bypass it with GitHub-hosted billing workarounds, a PAT, SSH, or VPS actions.

## Non-change confirmation

- .github/workflows/ci.yml was not modified.
- No workflow was dispatched in CD-3C.
- No GHCR login, image pull/build/push/tag/delete, package change, or registry inspection occurred in CD-3C.
- No SSH connection, VPS access, Docker/Compose production command, Caddy operation, database action, migration, or deployment occurred.
- No repository Secret, Variable, Environment, runner setting, package setting, or organization setting changed.
- No direct push to main, develop_v2, or develop occurred; PR #55 remains unmerged.
- CD-4B was not started.

**Stop point:** CD-3C ends after opening PR #55 and recording this report. Do not merge, dispatch, deploy, or start CD-4B from this phase.
