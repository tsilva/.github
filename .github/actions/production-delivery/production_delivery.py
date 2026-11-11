"""Deliver allowlisted production credentials, then deploy through GitHub Actions.

Provider responses and credential values never enter logs or workflow outputs.
Deployment credentials are supplied only to the step that needs them.
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INFISICAL = "https://app.infisical.com"
VERCEL = "https://api.vercel.com"
GITHUB = "https://api.github.com"
CLOUDFLARE = "https://api.cloudflare.com/client/v4"


class DeliveryError(Exception):
    """Only explicitly safe messages may reach the runner log."""


class ProviderHTTPError(DeliveryError):
    """Retain only the status code, never the provider response or credentials."""

    def __init__(self, status):
        self.status = status
        super().__init__(
            f"Provider request failed (HTTP {status}); response suppressed."
        )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeliveryError("Provider redirect rejected.")


def request(method, url, token=None, payload=None):
    headers = {"Content-Type": "application/json", "User-Agent": "production-delivery"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            req, timeout=60
        ) as response:
            if response.status == 204:
                return {}
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ProviderHTTPError(error.code) from None
    except DeliveryError:
        raise
    except Exception:
        raise DeliveryError("Provider request failed; details suppressed.") from None


def required(name):
    value = os.environ.get(name, "")
    if not value or any(c in value for c in "\r\n\0"):
        raise DeliveryError(
            "Required workflow credential/configuration is missing or invalid."
        )
    return value


def mask(value):
    # GitHub's masking command escaping also handles percent signs safely.
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::add-mask::" + value, flush=True)


def configuration():
    # Caller-controlled files and inputs never select the vault or destination.
    apps = json.loads(Path(__file__).with_name("apps.json").read_text())
    caller_id = required("GITHUB_REPOSITORY_ID")
    config = apps.get(caller_id)
    if not config or str(config["githubRepositoryId"]) != caller_id:
        raise DeliveryError("Unapproved caller repository; no credentials requested.")
    if required("GITHUB_REPOSITORY_OWNER_ID") != "26742":
        raise DeliveryError("Unexpected repository owner; no credentials requested.")
    if required("GITHUB_REPOSITORY") != config["repository"]:
        raise DeliveryError("Caller name and immutable repository ID disagree.")
    revision = required("SHARED_DELIVERY_REVISION")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise DeliveryError("Invalid trusted deployment revision.")
    return config


def context(config):
    if (
        required("GITHUB_REPOSITORY") != config["repository"]
        or required("GITHUB_REF") != "refs/heads/main"
        or not allowed_event(config)
        or required("GITHUB_WORKFLOW_REF")
        != config["repository"] + "/.github/workflows/production-delivery.yml@refs/heads/main"
    ):
        raise DeliveryError(
            "Workflow repository, branch, event or workflow path mismatch; no writes."
        )
    sha = required("GITHUB_SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise DeliveryError("Invalid commit SHA; no writes.")
    if required("GITHUB_EVENT_NAME") == "repository_dispatch":
        completion_event(config, sha)
    else:
        triggering_ci_run(config, sha)
    latest = request(
        "GET",
        GITHUB + "/repos/" + config["repository"] + "/git/ref/heads/main",
        required("GH_TOKEN"),
    )
    if latest["object"]["sha"] != sha:
        raise DeliveryError("This run is superseded by a newer main commit; no writes.")
    return sha


def validate_oidc(jwt, config):
    # Signature verification is performed by Infisical. These checks bind the
    # token from GitHub's authenticated runner endpoint to this exact job.
    try:
        parts = jwt.split(".")
        if len(parts) != 3:
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        expected = {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": INFISICAL,
            "repository": config["repository"],
            "repository_id": str(config["githubRepositoryId"]),
            "repository_owner_id": "26742",
            "ref": "refs/heads/main",
            "sha": required("GITHUB_SHA"),
            "environment": "Production",
            "workflow_ref": config["repository"]
            + "/.github/workflows/production-delivery.yml@refs/heads/main",
            "job_workflow_ref": "tsilva/.github/.github/workflows/production-delivery.yml@"
            + required("SHARED_DELIVERY_REVISION"),
        }
        if any(claims.get(key) != value for key, value in expected.items()):
            raise ValueError()
        if claims.get("event_name") != required("GITHUB_EVENT_NAME") or not allowed_event(config):
            raise ValueError()
        if claims["event_name"] == "repository_dispatch":
            completion_event(config, required("GITHUB_SHA"))
        now = time.time()
        if not now < claims["exp"] <= now + 900 or claims["iat"] > now + 30:
            raise ValueError()
    except Exception:
        raise DeliveryError(
            "GitHub OIDC claims do not identify the pinned trusted job; no login."
        ) from None


def workflow_oidc(config):
    """Obtain job identity only from GitHub's authenticated HTTPS endpoint."""
    url = required("ACTIONS_ID_TOKEN_REQUEST_URL")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".actions.githubusercontent.com")
    ):
        raise DeliveryError("Unexpected GitHub OIDC issuer endpoint; no writes.")
    separator = "&" if parsed.query else "?"
    jwt = request(
        "GET",
        url + separator + urllib.parse.urlencode({"audience": INFISICAL}),
        required("ACTIONS_ID_TOKEN_REQUEST_TOKEN"),
    )["value"]
    mask(jwt)
    validate_oidc(jwt, config)
    return jwt


def infisical_secrets(config):
    names = config["secretNames"]
    if not names:
        return {}
    if len(names) != len(set(names)) or any(
        not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) for name in names
    ):
        raise DeliveryError("Invalid pinned source allowlist; no writes.")
    if os.environ.get("GITHUB_EVENT_NAME") == "repository_dispatch":
        raise DeliveryError("Completion events cannot access Infisical or synchronize secrets.")
    jwt = workflow_oidc(config)
    login = request(
        "POST",
        INFISICAL + "/api/v1/auth/oidc-auth/login",
        payload={"identityId": config["identityId"], "jwt": jwt},
    )
    token = login["accessToken"]
    mask(token)
    query = urllib.parse.urlencode(
        {
            "projectId": config["infisicalProjectId"],
            "environment": "prod",
            "secretPath": "/",
            "type": "shared",
            "viewSecretValue": "true",
            "expandSecretReferences": "false",
            "includeImports": "false",
        }
    )
    values = {}
    for name in names:
        try:
            secret = request("GET", INFISICAL + "/api/v4/secrets/" + name + "?" + query, token)[
                "secret"
            ]
        except ProviderHTTPError as error:
            raise DeliveryError(
                f"Cannot read required Infisical production key {name} "
                f"(HTTP {error.status}); check its presence and reader access. No writes."
            ) from None
        value = secret.get("secretValue")
        if (
            secret.get("secretKey") != name
            or secret.get("workspace") != config["infisicalProjectId"]
            or secret.get("environment") != "prod"
            or secret.get("type") != "shared"
            or not isinstance(value, str)
            or not value
            or any(c in value for c in "\r\n\0")
        ):
            raise DeliveryError(
                "Required source secret is missing or has unexpected metadata; no writes."
            )
        mask(value)
        values[name] = value

    return values


def vercel_request(config, method, path, payload=None):
    join = "&" if "?" in path else "?"
    return request(
        method,
        VERCEL + path + join + "teamId=" + config["vercelTeamId"],
        required("VERCEL_TOKEN"),
        payload,
    )


def verify_vercel(config):
    project = vercel_request(config, "GET", "/v9/projects/" + config["vercelProjectId"])
    if (
        project.get("id") != config["vercelProjectId"]
        or project.get("accountId") != config["vercelTeamId"]
        or str(project.get("link", {}).get("repoId"))
        != str(config["githubRepositoryId"])
    ):
        raise DeliveryError(
            "Vercel team, project or linked repository mismatch; no writes."
        )


def production_matches(items, key):
    matches = [
        x for x in items if x.get("key") == key and "production" in x.get("target", [])
    ]
    if len(matches) > 1 or any(
        x.get("target") != ["production"] or x.get("gitBranch") for x in matches
    ):
        raise DeliveryError(
            "Duplicate or combined destination targets require review; no writes."
        )
    return matches


def config_names(config):
    names = config.get("configNames")
    allowed = {
        "ASSET_RETENTION_SECONDS",
        "NEON_REALTIME_URL",
        "OPENROUTER_APP_NAME",
        "OPENROUTER_MODEL",
        "OPENROUTER_SITE_URL",
        "R2_ACCOUNT_ID",
        "R2_BUCKET_NAME",
        "R2_ENDPOINT",
        "R2_OBJECT_PREFIX",
        "RESHOOT_PAYMENTS_MODE",
        "STRIPE_TEST_STARTER_MONTHLY_PRICE_ID",
        "STRIPE_TEST_STUDIO_MONTHLY_PRICE_ID",
        "STRIPE_TEST_PRO_MONTHLY_PRICE_ID",
        "STRIPE_TEST_PORTAL_CONFIGURATION_ID",
        "SENTRY_BASE_URL",
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_ORG",
        "SENTRY_PROJECT",
        "SENTRY_TRACES_SAMPLE_RATE",
        "TUBESCRIBE_PUBLIC_ORIGIN",
    }
    if (
        not isinstance(names, list)
        or any(not isinstance(name, str) for name in names)
        or len(names) != len(set(names))
        or any(name not in config["secretNames"] for name in names)
        or any(
            name not in allowed
            and not name.startswith(("NEXT_PUBLIC_", "PUBLIC_", "VITE_"))
            for name in names
        )
    ):
        raise DeliveryError("Invalid pinned public configuration allowlist; no writes.")
    return set(names)


def confirmed_variable(result, key):
    if result.get("failed"):
        # Emit only fixed codes; provider messages and arbitrary codes can contain credentials.
        known = {
            "bad_request",
            "forbidden",
            "not_found",
            "env_already_exists",
            "env_value_invalid_length",
        }
        failures = result["failed"] if isinstance(result["failed"], list) else []
        codes = []
        for failure in failures:
            error = failure.get("error", {}) if isinstance(failure, dict) else {}
            code = error.get("code") if isinstance(error, dict) else None
            if code in known:
                codes.append(code)
        reason = ", ".join(codes) or "unclassified"
        raise DeliveryError(
            f"Vercel rejected Production key {key} (code: {reason}); inspect its environment separation. "
            "Provider response suppressed."
        )
    created = result.get("created")
    if isinstance(created, list):
        created = created[0] if len(created) == 1 else None
    if not isinstance(created, dict) or created.get("key") != key:
        raise DeliveryError(
            f"Vercel did not confirm Production key {key}; response suppressed."
        )
    return created


def sync_vercel(config, values):
    public = config_names(config)
    if set(values) != set(config["secretNames"]):
        raise DeliveryError(
            "Source values do not match the pinned allowlist; no writes."
        )
    verify_vercel(config)
    path = "/v10/projects/" + config["vercelProjectId"] + "/env"
    before = vercel_request(config, "GET", path)["envs"]
    existing = {}
    # Validate every destination and migration before writing any key.
    for key in values:
        matches = production_matches(before, key)
        if matches:
            row = matches[0]
            if not isinstance(row.get("id"), str) or not row["id"]:
                raise DeliveryError(
                    "Production variable identifier is missing; no writes."
                )
            if row.get("customEnvironmentIds") or row.get("configurationId"):
                raise DeliveryError(
                    "Managed or custom-environment variable requires review; no writes."
                )
            existing[key] = row
    for key, value in values.items():
        print(f"Syncing Vercel Production key {key}.", flush=True)
        is_config = key in public
        kind = "encrypted" if is_config else "sensitive"
        visibility = "config" if is_config else "secret"
        payload = {
            "key": key,
            "value": value,
            "type": kind,
            "visibility": visibility,
            "target": ["production"],
            "comment": "Managed from Infisical by GitHub production-delivery",
        }
        row = existing.get(key)
        if row:
            env_path = (
                "/v9/projects/"
                + config["vercelProjectId"]
                + "/env/"
                + urllib.parse.quote(row["id"], safe="")
            )
            was_secret = row.get("visibility") == "secret" or (
                row.get("visibility") != "config" and row.get("type") == "sensitive"
            )
            if is_config and was_secret:
                # Vercel forbids Secret -> Config in place. Replace only this
                # explicitly classified Production row, using the loaded source.
                vercel_request(config, "DELETE", env_path)
                result = vercel_request(config, "POST", path, payload)
            else:
                # Supplying key would rename a Secret; preserve key and targets.
                update = {
                    k: v for k, v in payload.items() if k not in ("key", "target")
                }
                result = {"created": vercel_request(config, "PATCH", env_path, update)}
        else:
            result = vercel_request(config, "POST", path, payload)
        created = confirmed_variable(result, key)
        matches = production_matches(vercel_request(config, "GET", path)["envs"], key)
        if (
            len(matches) != 1
            or not created.get("id")
            or matches[0].get("id") != created["id"]
            or matches[0].get("type") != kind
            or matches[0].get("visibility", visibility) != visibility
        ):
            raise DeliveryError(
                f"Vercel Production metadata verification failed for {key}."
            )


def cloudflare_request(config, method, suffix, payload=None):
    path = (
        "/accounts/"
        + config["cloudflareAccountId"]
        + "/workers/scripts/"
        + config["workerName"]
        + suffix
    )
    result = request(
        method, CLOUDFLARE + path, required("CLOUDFLARE_API_TOKEN"), payload
    )
    if not result.get("success"):
        raise DeliveryError("Cloudflare request failed; response suppressed.")
    return result.get("result")


def sync_worker(config, value):
    before = cloudflare_request(config, "GET", "/secrets")
    if sum(x.get("name") == config["secretNames"][0] for x in before) != 1:
        raise DeliveryError("Expected existing Worker secret not found; no writes.")
    cloudflare_request(
        config,
        "PUT",
        "/secrets",
        {"name": config["secretNames"][0], "text": value, "type": "secret_text"},
    )
    after = cloudflare_request(config, "GET", "/secrets")
    if (
        sum(
            x.get("name") == config["secretNames"][0] and x.get("type") == "secret_text"
            for x in after
        )
        != 1
    ):
        raise DeliveryError("Worker secret metadata verification failed.")
    verify_worker_health(config)


def verify_worker_health(config):
    health = request("GET", config["healthUrl"])
    if health.get("provider") != "openai" or not health.get("configured"):
        raise DeliveryError(
            "Worker health does not confirm the configured OpenAI provider."
        )


def validate_ci_run(run, config, sha):
    """Accept only the approved repository's successful main-push CI."""
    try:
        for key in ("id", "workflow_id", "run_number", "run_attempt"):
            if type(run[key]) is not int or run[key] <= 0:
                raise ValueError()
        expected = {
            "path": ".github/workflows/ci.yml",
            "event": "push",
            "head_branch": "main",
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
        }
        if any(run.get(key) != value for key, value in expected.items()):
            raise ValueError()
        for key in ("repository", "head_repository"):
            repo = run[key]
            if (
                type(repo["id"]) is not int
                or repo["id"] != config["githubRepositoryId"]
                or repo["full_name"] != config["repository"]
            ):
                raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise DeliveryError(
            "CI must be a successful main-push run of the approved ci.yml for this exact commit; no writes."
        ) from None


def triggering_ci_run(config, sha):
    # workflow_run's GITHUB_SHA is the default-branch tip, not necessarily the
    # triggering CI commit. Reject stale events instead of deploying that tip.
    if required("GITHUB_EVENT_NAME") != "workflow_run":
        return None
    try:
        event = json.loads(Path(required("GITHUB_EVENT_PATH")).read_text())
        repo = event["repository"]
        if (
            event["action"] != "completed"
            or type(repo["id"]) is not int
            or repo["id"] != config["githubRepositoryId"]
            or repo["full_name"] != config["repository"]
        ):
            raise ValueError()
        run = event["workflow_run"]
        validate_ci_run(run, config, sha)
        return run
    except (OSError, KeyError, TypeError, ValueError):
        raise DeliveryError("Invalid completed CI event; no credentials requested.") from None


def verify_ci(config, sha):
    """Recheck CI once; pending, failed or superseded CI never holds a runner."""
    trigger = triggering_ci_run(config, sha)
    url = (
        GITHUB
        + "/repos/"
        + config["repository"]
        + "/actions/workflows/ci.yml/runs?"
        + urllib.parse.urlencode(
            {"head_sha": sha, "branch": "main", "event": "push", "per_page": 10}
        )
    )
    try:
        runs = request("GET", url, required("GH_TOKEN"))["workflow_runs"]
        candidates = [run for run in runs if run.get("head_sha") == sha]
        if not candidates or any(type(run.get("run_number")) is not int for run in candidates):
            raise ValueError()
        latest = max(candidates, key=lambda run: run["run_number"])
        validate_ci_run(latest, config, sha)
        if trigger and any(
            latest[key] != trigger[key]
            for key in ("id", "workflow_id", "run_attempt", "run_number")
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise DeliveryError(
            "The latest exact-commit CI run must already have succeeded; delivery held without waiting."
        ) from None
    return latest


def event_driven(config):
    # Event-driven rollout is deliberately restricted to this immutable caller.
    return (
        config.get("eventDrivenDelivery") is True
        and config.get("repository") == "tsilva/tubescribe"
        and config.get("githubRepositoryId") == 1411588422
        and config.get("destination") == "vercel"
        and config.get("productionDomains") == ["tubescribe.tsilva.eu"]
    )


def allowed_event(config):
    event = required("GITHUB_EVENT_NAME")
    return event in ("workflow_run", "workflow_dispatch") or (
        event == "repository_dispatch" and event_driven(config)
    )


def completion_event(config, sha):
    """The event is a hint; deployment state and receipt are verified separately."""
    try:
        if not event_driven(config) or required("GITHUB_EVENT_NAME") != "repository_dispatch":
            raise ValueError()
        event = json.loads(Path(required("GITHUB_EVENT_PATH")).read_text())
        if event["action"] not in (
            "vercel.deployment.success",
            "vercel.deployment.error",
            "vercel.deployment.canceled",
            "vercel.deployment.failed",
            "vercel.deployment.ignored",
            "vercel.deployment.skipped",
        ):
            raise ValueError()
        repo, sender, payload = event["repository"], event["sender"], event["client_payload"]
        if (
            type(repo["id"]) is not int
            or repo["id"] != config["githubRepositoryId"]
            or repo["full_name"] != config["repository"]
            or type(sender["id"]) is not int
            or sender["id"] != 35613825
            or sender["login"] != "vercel[bot]"
            or sender["type"] != "Bot"
            or required("GITHUB_ACTOR_ID") != "35613825"
            or payload["project"]["id"] != config["vercelProjectId"]
            or payload["project"]["name"] != config["vercelProjectName"]
            or payload["environment"] != "production"
            or payload["git"]["sha"] != sha
            or payload["git"]["ref"] not in ("main", "refs/heads/main", sha)
            or payload["state"]["type"] != event["action"].removeprefix("vercel.deployment.")
        ):
            raise ValueError()
        return event["action"], payload
    except (OSError, KeyError, TypeError, ValueError):
        raise DeliveryError(
            "Unapproved Vercel completion event; no credentials requested."
        ) from None


def positive_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise DeliveryError("Missing or invalid trusted delivery receipt.")
    return int(value)


def deployment_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"dpl_[A-Za-z0-9]{1,64}", value):
        raise DeliveryError("Invalid deployment identity; no provider request.")
    return value


def verify_delivery_receipt(config, sha, deployment, ci):
    meta = deployment.get("meta", {})
    if (
        meta.get("infisicalDeliveryProtocol") != "events-v1"
        or meta.get("infisicalDeliveryCommit") != sha
        or meta.get("githubCommitSha") != sha
        or meta.get("infisicalDeliveryRevision") != required("SHARED_DELIVERY_REVISION")
        or positive_id(meta.get("infisicalDeliveryCiRun")) != ci["id"]
        or positive_id(meta.get("infisicalDeliveryCiAttempt")) != ci["run_attempt"]
    ):
        raise DeliveryError("Deployment does not match this trusted exact-commit CI receipt.")
    run_id = positive_id(meta.get("infisicalDeliveryRun"))
    attempt = positive_id(meta.get("infisicalDeliveryRunAttempt"))
    run = request(
        "GET",
        GITHUB + "/repos/" + config["repository"] + "/actions/runs/" + str(run_id),
        required("GH_TOKEN"),
    )
    try:
        for key in ("id", "workflow_id", "run_number", "run_attempt"):
            if type(run[key]) is not int or run[key] <= 0:
                raise ValueError()
        if (
            run["id"] != run_id
            or run["run_attempt"] != attempt
            or run["path"] != ".github/workflows/production-delivery.yml"
            or run["head_sha"] != sha
            or run["head_branch"] != "main"
            or run["event"] not in ("workflow_run", "workflow_dispatch")
            or not (
                (run["status"] == "completed" and run["conclusion"] == "success")
                or (run["status"] == "in_progress" and run["conclusion"] is None)
            )
        ):
            raise ValueError()
        for key in ("repository", "head_repository"):
            if (
                type(run[key]["id"]) is not int
                or run[key]["id"] != config["githubRepositoryId"]
                or run[key]["full_name"] != config["repository"]
            ):
                raise ValueError()
        revision = required("SHARED_DELIVERY_REVISION")
        expected = "tsilva/.github/.github/workflows/production-delivery.yml@" + revision
        if not any(
            x.get("path") == expected and x.get("sha") == revision
            for x in run["referenced_workflows"]
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise DeliveryError(
            "Deployment's initiating trusted workflow or attempt could not be verified."
        ) from None


def complete_vercel(config):
    if not event_driven(config):
        raise DeliveryError("Event-driven completion is not enabled for this caller.")
    sha = context(config)
    if required("GITHUB_EVENT_NAME") == "repository_dispatch":
        action, payload = completion_event(config, sha)
        if action != "vercel.deployment.success":
            raise DeliveryError(
                "Vercel reported deployment failure or cancellation; production is not verified."
            )
        identifier = deployment_id(payload.get("id"))
    elif required("GITHUB_EVENT_NAME") == "workflow_dispatch":
        identifier = deployment_id(required("VERIFY_DEPLOYMENT_ID"))
    else:
        raise DeliveryError("Completion requires a trusted event or explicit manual verification.")
    ci = verify_ci(config, sha)
    workflow_oidc(config)
    verify_vercel(config)
    deployment = vercel_request(config, "GET", "/v13/deployments/" + identifier)
    if (
        deployment.get("id") != identifier
        or deployment.get("projectId") != config["vercelProjectId"]
        or deployment.get("target") != "production"
        or deployment.get("readyState", deployment.get("status")) != "READY"
        or not production_aliases_assigned(deployment)
    ):
        raise DeliveryError(
            "Production is not READY with all required checks and domain assignment; no polling."
        )
    verify_delivery_receipt(config, sha, deployment, ci)
    for domain in config["productionDomains"]:
        alias = vercel_request(
            config,
            "GET",
            "/v4/aliases/"
            + urllib.parse.quote(domain, safe="")
            + "?projectId="
            + config["vercelProjectId"],
        )
        if (
            alias.get("alias") != domain
            or alias.get("projectId") != config["vercelProjectId"]
            or alias.get("deploymentId") != identifier
        ):
            raise DeliveryError("Production domain does not serve this exact deployment.")
    context(config)
    print("Production READY: " + identifier + " commit " + sha)


def production_aliases_assigned(deployment):
    if deployment.get("aliasError"):
        raise DeliveryError(
            "Production domain assignment failed; inspect Vercel deployment checks."
        )
    assigned = deployment.get("aliasAssigned")
    # Vercel returns a boolean or the assignment timestamp, depending on API view.
    return assigned is True or (type(assigned) is int and assigned > 0)


def deploy_vercel(config, sha):
    if os.environ.get("GITHUB_EVENT_NAME") == "repository_dispatch":
        raise DeliveryError("Completion events cannot create deployments.")
    ci = verify_ci(config, sha)
    context(config)
    verify_vercel(config)
    payload = {
        "name": config["vercelProjectName"],
        "project": config["vercelProjectId"],
        "target": "production",
        "gitSource": {"type": "github", "repoId": str(config["githubRepositoryId"]), "ref": sha},
        "meta": {"infisicalDeliveryCommit": sha, "infisicalDeliveryRun": required("GITHUB_RUN_ID")},
    }
    if event_driven(config):
        workflow_oidc(config)
        positive_id(required("GITHUB_RUN_ID"))
        positive_id(required("GITHUB_RUN_ATTEMPT"))
        payload["meta"].update(
            {
                "infisicalDeliveryProtocol": "events-v1",
                "infisicalDeliveryRunAttempt": required("GITHUB_RUN_ATTEMPT"),
                "infisicalDeliveryRevision": required("SHARED_DELIVERY_REVISION"),
                "infisicalDeliveryCiRun": str(ci["id"]),
                "infisicalDeliveryCiAttempt": str(ci["run_attempt"]),
            }
        )
    result = vercel_request(
        config,
        "POST",
        "/v13/deployments",
        payload,
    )
    deployment_id = result.get("id")
    if not isinstance(deployment_id, str) or not deployment_id.startswith("dpl_"):
        raise DeliveryError("Deployment creation was not confirmed; response suppressed.")
    if event_driven(config):
        if not re.fullmatch(r"dpl_[A-Za-z0-9]+", deployment_id):
            raise DeliveryError("Deployment creation returned an invalid identity.")
        context(config)
        print(
            "Production submitted: "
            + deployment_id
            + " commit "
            + sha
            + "; awaiting verified Vercel completion event."
        )
        return
    deadline = time.monotonic() + 1500
    while time.monotonic() < deadline:
        deployment = vercel_request(config, "GET", "/v13/deployments/" + deployment_id)
        if (
            deployment.get("projectId") != config["vercelProjectId"]
            or deployment.get("target") != "production"
        ):
            raise DeliveryError("Deployment target verification failed.")
        state = deployment.get("readyState", deployment.get("status"))
        if state in ("ERROR", "CANCELED"):
            raise DeliveryError("Vercel production build failed; inspect the deployment in Vercel.")
        if state == "READY":
            if deployment.get("meta", {}).get("githubCommitSha") != sha:
                raise DeliveryError("Deployment commit verification failed.")
            if production_aliases_assigned(deployment):
                context(config)
                print("Production READY: " + deployment_id + " commit " + sha)
                return
        time.sleep(15)
    raise DeliveryError(
        "Vercel release timed out; inspect build, required checks and "
        "Production domain assignment before retrying."
    )


def main():
    if sys.argv[1:] not in (["sync"], ["deploy"], ["check"], ["worker-health"], ["complete"]):
        raise DeliveryError("Use only the fixed check, sync, deploy or complete operation.")
    config = configuration()
    sha = context(config)
    if required("GITHUB_EVENT_NAME") == "repository_dispatch" and sys.argv[1] not in (
        "check",
        "complete",
    ):
        raise DeliveryError("Completion events cannot request deployment or secret writes.")
    if sys.argv[1] == "complete":
        complete_vercel(config)
    elif sys.argv[1] == "check":
        verify_ci(config, sha)
        context(config)
        print("CI passed for commit " + sha)
    elif sys.argv[1] == "worker-health":
        verify_worker_health(config)
        print("Worker health verified.")
    elif sys.argv[1] == "deploy":
        deploy_vercel(config, sha)
    else:
        verify_ci(config, sha)
        values = infisical_secrets(config)
        context(config)
        if config["destination"] == "vercel":
            sync_vercel(config, values)
        elif config["destination"] == "cloudflare-worker":
            sync_worker(config, values[config["secretNames"][0]])
            verify_vercel(config)
        else:
            raise DeliveryError("Unsupported pinned destination; no writes.")
        print(str(len(values)) + " allowlisted keys synced; destination metadata verified.")


if __name__ == "__main__":
    try:
        main()
    except DeliveryError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Production delivery failed; private details suppressed.", file=sys.stderr)
        sys.exit(1)
