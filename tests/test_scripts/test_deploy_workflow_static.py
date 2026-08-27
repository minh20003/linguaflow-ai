#!/usr/bin/env python3
"""Static contract checks for the BTC shared-runner artifact workflow."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-production.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def step(job: dict[str, object], name: str) -> dict[str, object]:
    for item in job.get("steps", []):
        if isinstance(item, dict) and item.get("name") == name:
            return item
    raise AssertionError(f"missing workflow step: {name}")


def main() -> int:
    ci_before = hashlib.sha256(CI_WORKFLOW.read_bytes()).hexdigest()
    raw = WORKFLOW.read_text(encoding="utf-8")
    document = yaml.load(raw, Loader=yaml.BaseLoader)

    require(isinstance(document, dict), "workflow YAML must parse as a mapping")
    dispatch = document.get("on", {}).get("workflow_dispatch", {})
    release_input = dispatch.get("inputs", {}).get("release_sha", {})
    require(release_input.get("required") == "true", "release_sha must be required")
    require(release_input.get("type") == "string", "release_sha must be a string")

    require("ubuntu-latest" not in raw, "artifact workflow must not target ubuntu-latest")
    require("runs-on: [" not in raw, "BTC did not authorize speculative runner labels")
    jobs = document.get("jobs", {})
    require(set(jobs) == {"gate", "build-or-reuse"}, "workflow job graph must stay gate -> build-or-reuse")
    for job_name, job in jobs.items():
        require(job.get("runs-on") == "self-hosted", f"{job_name} must use exactly self-hosted")

    concurrency = document.get("concurrency", {})
    require(concurrency.get("group") == "linguaflow-production", "wrong production concurrency group")
    require(concurrency.get("cancel-in-progress") == "false", "production runs must queue")

    gate = jobs["gate"]
    require(gate.get("permissions") == {"contents": "read", "actions": "read"}, "gate permissions must stay read-only")
    gate_prereq = step(gate, "Verify shared runner Gate prerequisites")["run"]
    for required in ("command -v \"$binary\"", "bash git gh jq", "git --version", "gh --version", "jq --version"):
        require(required in gate_prereq, f"Gate runner prerequisite is missing {required}")
    require("sudo" not in gate_prereq, "workflow must not install or mutate host tools with sudo")
    release_gate = step(gate, "Validate immutable SHA and develop_v2 ancestry")["run"]
    for required in (
        "^[0-9A-Fa-f]{40}$",
        'release_sha="${RELEASE_SHA_INPUT,,}"',
        "git cat-file -e",
        "git merge-base --is-ancestor",
        "origin/develop_v2",
    ):
        require(required in release_gate, f"release gate is missing {required}")
    ci_gate = step(gate, "Require successful push CI for this exact SHA")["run"]
    for required in (
        "actions/workflows/ci.yml/runs?event=push",
        '.event == "push"',
        ".head_sha == $sha",
        '.conclusion == "success"',
    ):
        require(required in ci_gate, f"CI gate is missing {required}")

    build = jobs["build-or-reuse"]
    require(build.get("needs") == "gate", "build must depend on gate")
    require(build.get("permissions") == {"contents": "read", "packages": "write"}, "build permissions must be least privilege")
    checkout = step(build, "Checkout the approved release SHA")
    require(
        checkout.get("with", {}).get("ref") == "${{ needs.gate.outputs.release_sha }}",
        "build checkout must use the validated release SHA",
    )
    require("github.sha" not in raw, "workflow must not use workflow-definition github.sha")

    public_config = step(build, "Require public frontend build configuration")
    public_env = public_config["env"]
    require(public_env.get("NEXT_PUBLIC_API_URL") == "${{ vars.NEXT_PUBLIC_API_URL }}", "API URL must use Variables")
    require(
        public_env.get("NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID") == "${{ vars.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID }}",
        "OAuth client ID must use Variables",
    )

    docker_prereq = step(build, "Verify Docker and Buildx prerequisites on shared runner")["run"]
    for required in ("command -v docker", "docker version", "docker buildx version"):
        require(required in docker_prereq, f"runner prerequisite is missing {required}")
    require("sudo" not in docker_prereq, "workflow must not install or mutate host Docker with sudo")

    login = step(build, "Log in to GitHub Container Registry")
    login_options = login.get("with", {})
    require(login.get("uses") == "docker/login-action@v3", "must use docker/login-action")
    require(login_options.get("registry") == "ghcr.io", "GHCR registry must be explicit")
    require(login_options.get("username") == "${{ github.actor }}", "GHCR username must be github.actor")
    require(login_options.get("password") == "${{ secrets.GITHUB_TOKEN }}", "GHCR must use job-scoped GITHUB_TOKEN")
    require(login_options.get("logout") == "true", "GHCR login must logout after the job")

    buildx = step(build, "Set up Docker Buildx")
    buildx_options = buildx.get("with", {})
    require(buildx.get("uses") == "docker/setup-buildx-action@v3", "must use standard Buildx setup action")
    require(buildx_options.get("install") == "false", "workflow must not globally install Buildx")
    require(buildx_options.get("cleanup") == "true", "Buildx temporary builder must be cleaned up")
    require(buildx_options.get("keep-state") == "false", "shared runner must not retain BuildKit state")

    images = step(build, "Define immutable image references")["run"]
    require("p-217-backend:$RELEASE_SHA" in images, "backend image must use full SHA tag")
    require("p-217-frontend:$RELEASE_SHA" in images, "frontend image must use full SHA tag")
    require(":latest" not in raw.lower(), "workflow must not reference latest")

    image_state = step(build, "Determine exact-SHA image state without overwrite")["run"]
    require("docker buildx imagetools inspect" in image_state, "exact-SHA image inspection is missing")
    require("PARTIAL RELEASE STATE" in image_state, "partial release state must fail closed")
    require("image_status=build" in image_state and "image_status=reuse" in image_state, "build/reuse state output is missing")

    reuse = step(build, "Validate existing immutable image metadata")["run"]
    require("org.opencontainers.image.revision" in reuse, "existing-image revision validation is missing")
    require("RepoDigests" in reuse, "existing-image digest evidence is missing")

    backend = step(build, "Build and publish backend image")
    frontend = step(build, "Build and publish frontend image")
    for build_step, scope in ((backend, "linguaflow-backend"), (frontend, "linguaflow-frontend")):
        options = build_step["with"]
        require(options.get("push") == "true", "immutable images must be pushed")
        require(f"scope={scope}" in options.get("cache-from", ""), f"missing {scope} cache-from")
        require(f"scope={scope}" in options.get("cache-to", ""), f"missing {scope} cache-to")
        labels = options.get("labels", "")
        require("org.opencontainers.image.revision=${{ needs.gate.outputs.release_sha }}" in labels, "missing OCI revision label")
        require("org.opencontainers.image.source=https://github.com/AI20K-Build-Phase-Cohort-3/P-217" in labels, "missing OCI source label")

    frontend_args = frontend["with"].get("build-args", "")
    require("NEXT_PUBLIC_API_URL=${{ vars.NEXT_PUBLIC_API_URL }}" in frontend_args, "frontend API URL build arg is missing")
    require("NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID=${{ vars.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID }}" in frontend_args, "frontend OAuth build arg is missing")

    secret_names = set(re.findall(r"secrets\.([A-Z0-9_]+)", raw))
    require(secret_names == {"GITHUB_TOKEN"}, "workflow must not reference runtime application secrets")
    for forbidden in (
        "ssh",
        "scp",
        "deploy_release.sh",
        "production.env",
        "/opt/linguaflow",
        "alembic",
        "sudo",
        "apt-get",
        "yum install",
        "dnf install",
        "apk add",
    ):
        require(forbidden not in raw.lower(), f"workflow must not contain {forbidden}")

    expected_outputs = {"release_sha", "backend_image", "frontend_image", "backend_digest", "frontend_digest", "image_status"}
    require(expected_outputs <= set(build.get("outputs", {})), "missing safe build outputs")
    require("steps.build_backend.outputs.digest" in raw, "new-build backend digest is not recorded")
    require("steps.build_frontend.outputs.digest" in raw, "new-build frontend digest is not recorded")

    ci_after = hashlib.sha256(CI_WORKFLOW.read_bytes()).hexdigest()
    require(ci_before == ci_after, "ci.yml changed during static validation")
    print("BTC shared-runner workflow static validation passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, TypeError, yaml.YAMLError) as error:
        print(f"test_deploy_workflow_static: {error}", file=sys.stderr)
        raise SystemExit(1)
