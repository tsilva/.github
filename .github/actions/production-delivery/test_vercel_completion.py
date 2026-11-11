"""Event data never authorizes deployment writes or substitutes for provider proof."""

import base64
import copy
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "events_delivery", Path(__file__).with_name("production_delivery.py")
)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class VercelCompletion(unittest.TestCase):
    config_id = "1411588422"

    def setUp(self):
        self.sha, self.revision = "a" * 40, "b" * 40
        self.config = json.loads(Path(__file__).with_name("apps.json").read_text())[self.config_id]
        self.repo = {
            "id": self.config["githubRepositoryId"],
            "full_name": self.config["repository"],
        }
        self.ci = {
            "id": 123,
            "workflow_id": 124,
            "run_number": 125,
            "run_attempt": 2,
            "repository": self.repo,
            "head_repository": self.repo,
            "path": ".github/workflows/ci.yml",
            "event": "push",
            "head_branch": "main",
            "head_sha": self.sha,
            "status": "completed",
            "conclusion": "success",
        }
        self.run = {
            "id": 456,
            "workflow_id": 457,
            "run_number": 458,
            "run_attempt": 1,
            "repository": self.repo,
            "head_repository": self.repo,
            "path": ".github/workflows/production-delivery.yml",
            "event": "workflow_run",
            "head_sha": self.sha,
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "referenced_workflows": [
                {
                    "path": "tsilva/.github/.github/workflows/production-delivery.yml@"
                    + self.revision,
                    "sha": self.revision,
                }
            ],
        }
        self.meta = {
            "githubCommitSha": self.sha,
            "infisicalDeliveryCommit": self.sha,
            "infisicalDeliveryRun": "456",
            "infisicalDeliveryRunAttempt": "1",
            "infisicalDeliveryCiRun": "123",
            "infisicalDeliveryCiAttempt": "2",
            "infisicalDeliveryRevision": self.revision,
            "infisicalDeliveryProtocol": "events-v1",
        }
        self.deployment = {
            "id": "dpl_test",
            "projectId": self.config["vercelProjectId"],
            "target": "production",
            "readyState": "READY",
            "aliasAssigned": True,
            "meta": self.meta,
        }
        self.event = {
            "action": "vercel.deployment.success",
            "repository": self.repo,
            "sender": {"id": 35613825, "login": "vercel[bot]", "type": "Bot"},
            "client_payload": {
                "id": "dpl_test",
                "project": {
                    "id": self.config["vercelProjectId"],
                    "name": self.config["vercelProjectName"],
                },
                "environment": "production",
                "git": {"sha": self.sha, "ref": "main"},
                "state": {"type": "success"},
                "url": "https://attacker.invalid/do-not-fetch",
            },
        }
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "event.json"
        self.save_event()
        self.env = {
            "GITHUB_REPOSITORY": self.config["repository"],
            "GITHUB_REPOSITORY_ID": self.config_id,
            "GITHUB_REPOSITORY_OWNER_ID": "26742",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": self.sha,
            "GITHUB_WORKFLOW_REF": self.config["repository"]
            + "/.github/workflows/production-delivery.yml@refs/heads/main",
            "GITHUB_EVENT_NAME": "repository_dispatch",
            "GITHUB_EVENT_PATH": str(self.path),
            "GITHUB_ACTOR_ID": "35613825",
            "SHARED_DELIVERY_REVISION": self.revision,
            "GH_TOKEN": "fake-github",
            "VERCEL_TOKEN": "fake-vercel",
            "GITHUB_RUN_ID": "456",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def save_event(self):
        self.path.write_text(json.dumps(self.event))

    def github(self, method, url, *args, **kwargs):
        self.assertEqual(method, "GET")
        if "/git/ref/heads/main" in url:
            return {"object": {"sha": self.sha}}
        if "/actions/workflows/ci.yml/runs?" in url:
            return {"workflow_runs": [self.ci]}
        if url.endswith("/actions/runs/456"):
            return self.run
        self.fail("Unexpected request destination")

    def vercel(self, config, method, path, payload=None):
        self.assertEqual(method, "GET", "Completion must be read-only")
        if path == "/v13/deployments/dpl_test":
            return self.deployment
        for domain in self.config["productionDomains"]:
            if path == "/v4/aliases/" + domain + "?projectId=" + self.config["vercelProjectId"]:
                return {
                    "alias": domain,
                    "projectId": self.config["vercelProjectId"],
                    "deploymentId": "dpl_test",
                }
        self.fail("Unexpected provider request destination")

    def complete(self):
        with (
            patch.object(d, "request", side_effect=self.github),
            patch.object(d, "vercel_request", side_effect=self.vercel),
            patch.object(d, "workflow_oidc") as identity,
            patch.object(d, "verify_vercel"),
            patch.object(d, "infisical_secrets", side_effect=AssertionError("No Infisical reads")),
            patch.object(d.time, "sleep", side_effect=AssertionError("No runner polling")),
        ):
            d.complete_vercel(self.config)
            identity.assert_called_once_with(self.config)

    def test_success_uses_provider_receipt_and_current_domain_not_event_url(self):
        self.complete()

    def test_forged_sender_repository_preview_project_and_stale_sha_fail_before_network(self):
        cases = [
            ("sender", "id", 26742),
            ("sender", "login", "attacker"),
            ("sender", "type", "User"),
            ("repository", "id", 1),
            ("repository", "full_name", "attacker/tubescribe"),
        ]
        original = copy.deepcopy(self.event)
        for section, key, value in cases:
            self.event = copy.deepcopy(original)
            self.event[section][key] = value
            self.save_event()
            with self.subTest(section=section, key=key), patch.object(d, "request") as request:
                with self.assertRaises(d.DeliveryError):
                    d.context(self.config)
                request.assert_not_called()
        for field, value in [
            ("environment", "preview"),
            ("project", {"id": "prj_other", "name": "tubescribe"}),
            ("git", {"sha": "c" * 40, "ref": "main"}),
            ("state", {"type": "ready"}),
        ]:
            self.event = copy.deepcopy(original)
            self.event["client_payload"][field] = value
            self.save_event()
            with self.subTest(field=field), patch.object(d, "request") as request:
                with self.assertRaises(d.DeliveryError):
                    d.context(self.config)
                request.assert_not_called()

    def test_event_actor_and_non_main_context_cannot_use_credentials(self):
        for key, value in [("GITHUB_ACTOR_ID", "26742"), ("GITHUB_REF", "refs/heads/feature")]:
            with patch.dict(os.environ, {key: value}), patch.object(d, "request") as request:
                with self.assertRaises(d.DeliveryError):
                    d.context(self.config)
                request.assert_not_called()

    def test_other_callers_cannot_enable_event_mode(self):
        for change in [
            {"githubRepositoryId": 123},
            {"repository": "tsilva/other"},
            {"productionDomains": ["attacker.invalid"]},
            {"eventDrivenDelivery": False},
        ]:
            config = self.config | change
            with patch.object(d, "request") as request:
                with self.assertRaises(d.DeliveryError):
                    d.context(config)
                request.assert_not_called()

    def test_prebuilt_and_worker_callers_cannot_enable_events(self):
        apps = json.loads(Path(__file__).with_name("apps.json").read_text())
        for config in apps.values():
            if config["githubRepositoryId"] in (1411588422, 1325113680, 1420482088):
                continue
            forged = config | {
                "eventDrivenDelivery": True,
                "productionDomains": ["attacker.invalid"],
            }
            with self.subTest(repository=config["repository"]):
                self.assertFalse(d.event_driven(forged))

    def test_early_ready_checks_alias_errors_and_wrong_targets_never_pass(self):
        original = copy.deepcopy(self.deployment)
        for change in [
            {"readyState": "BUILDING"},
            {"readyState": "ERROR"},
            {"readyState": "CANCELED"},
            {"target": "preview"},
            {"projectId": "prj_other"},
            {"id": "dpl_other"},
            {"aliasAssigned": False},
            {"aliasError": {"message": "private-provider-detail"}},
        ]:
            self.deployment = original | change
            with self.subTest(change=change), self.assertRaises(d.DeliveryError):
                self.complete()

    def test_replaced_domain_cannot_verify_an_older_deployment(self):
        old = self.vercel

        def provider(config, method, path, payload=None):
            if path.startswith("/v4/aliases/"):
                return {
                    "alias": self.config["productionDomains"][0],
                    "projectId": self.config["vercelProjectId"],
                    "deploymentId": "dpl_newer",
                }
            return old(config, method, path, payload)

        self.vercel = provider
        with self.assertRaises(d.DeliveryError):
            self.complete()

    def test_every_pinned_domain_must_point_to_the_verified_deployment(self):
        original = self.vercel
        for domain in self.config["productionDomains"]:

            def provider(config, method, path, payload=None):
                if path.startswith("/v4/aliases/" + domain + "?"):
                    return {
                        "alias": domain,
                        "projectId": self.config["vercelProjectId"],
                        "deploymentId": "dpl_other",
                    }
                return original(config, method, path, payload)

            self.vercel = provider
            with self.subTest(domain=domain), self.assertRaises(d.DeliveryError):
                self.complete()
        self.vercel = original

    def test_missing_forged_or_replayed_receipts_never_pass(self):
        original = self.meta.copy()
        for change in [
            {"infisicalDeliveryProtocol": "legacy"},
            {"githubCommitSha": "c" * 40},
            {"infisicalDeliveryCommit": "c" * 40},
            {"infisicalDeliveryRevision": "c" * 40},
            {"infisicalDeliveryCiRun": "124"},
            {"infisicalDeliveryCiAttempt": "1"},
            {"infisicalDeliveryRun": "../other"},
            {"infisicalDeliveryRunAttempt": "2"},
        ]:
            self.deployment["meta"] = original | change
            with self.subTest(change=change), self.assertRaises(d.DeliveryError):
                self.complete()

    def test_original_initiator_must_be_the_same_trusted_run_and_attempt(self):
        original = copy.deepcopy(self.run)
        for change in [
            {"path": ".github/workflows/ci.yml"},
            {"head_sha": "c" * 40},
            {"head_branch": "feature"},
            {"event": "pull_request"},
            {"run_attempt": 2},
            {"conclusion": "failure"},
            {"status": "queued"},
            {"repository": {"id": 1, "full_name": "tsilva/tubescribe"}},
            {"referenced_workflows": []},
            {"id": True},
        ]:
            self.run = original | change
            with self.subTest(change=change), self.assertRaises(d.DeliveryError):
                self.complete()

    def test_callback_may_arrive_before_initiator_post_job_cleanup_finishes(self):
        self.run.update(status="in_progress", conclusion=None)
        self.complete()

    def test_failed_or_newly_rerun_ci_blocks_completion(self):
        for change in [
            {"conclusion": "failure"},
            {"status": "in_progress", "conclusion": None},
            {"run_attempt": 3},
        ]:
            original = self.ci
            self.ci = original | change
            with self.subTest(change=change), self.assertRaises(d.DeliveryError):
                self.complete()
            self.ci = original

    def test_failure_callback_cannot_report_ready_or_read_secret_providers(self):
        for state in ["error", "canceled", "failed", "ignored", "skipped"]:
            self.event["action"] = "vercel.deployment." + state
            self.event["client_payload"]["state"]["type"] = state
            self.event["client_payload"].pop("id", None)
            self.save_event()
            with (
                patch.object(d, "request", side_effect=self.github),
                patch.object(d, "vercel_request") as provider,
                patch.object(d, "workflow_oidc") as identity,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.complete_vercel(self.config)
                provider.assert_not_called()
                identity.assert_not_called()

    def test_completion_cannot_read_infisical_or_launch_another_deployment(self):
        with patch.object(d, "request") as request:
            with self.assertRaises(d.DeliveryError):
                d.infisical_secrets(self.config)
            request.assert_not_called()
        for operation in ["deploy", "sync", "worker-health"]:
            with (
                patch.object(d.sys, "argv", ["production_delivery.py", operation]),
                patch.object(d, "request", side_effect=self.github),
                patch.object(d, "vercel_request") as provider,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.main()
                provider.assert_not_called()

    def test_untrusted_deployment_ids_cannot_select_request_paths(self):
        for value in [
            "../secrets",
            "dpl_test/../../env",
            "dpl_test?token=x",
            "https://attacker.invalid",
            None,
        ]:
            self.event["client_payload"]["id"] = value
            self.save_event()
            with (
                patch.object(d, "request", side_effect=self.github),
                patch.object(d, "vercel_request") as provider,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.complete_vercel(self.config)
                provider.assert_not_called()

    def test_manual_recovery_is_a_read_only_recheck_not_a_redeploy(self):
        os.environ.update(GITHUB_EVENT_NAME="workflow_dispatch", VERIFY_DEPLOYMENT_ID="dpl_test")
        self.complete()

    def test_async_submission_records_provenance_and_does_not_poll(self):
        os.environ["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        with (
            patch.object(d, "request", side_effect=self.github),
            patch.object(d, "workflow_oidc"),
            patch.object(d, "verify_vercel"),
            patch.object(d, "vercel_request", return_value={"id": "dpl_test"}) as provider,
            patch.object(d.time, "sleep", side_effect=AssertionError("No polling")),
        ):
            d.deploy_vercel(self.config, self.sha)
        provider.assert_called_once()
        config, method, path, payload = provider.call_args.args
        self.assertEqual((method, path), ("POST", "/v13/deployments"))
        self.assertEqual(payload["gitSource"]["ref"], self.sha)
        self.assertEqual(payload["target"], "production")
        for key, value in self.meta.items():
            if key != "githubCommitSha":
                self.assertEqual(payload["meta"][key], value)

    def test_oidc_binds_completion_to_the_same_trusted_job(self):
        claims = {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": d.INFISICAL,
            "repository": self.config["repository"],
            "repository_id": self.config_id,
            "repository_owner_id": "26742",
            "ref": "refs/heads/main",
            "sha": self.sha,
            "environment": "Production",
            "workflow_ref": self.env["GITHUB_WORKFLOW_REF"],
            "job_workflow_ref": "tsilva/.github/.github/workflows/production-delivery.yml@"
            + self.revision,
            "event_name": "repository_dispatch",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
        }

        def token(value):
            return (
                "header."
                + base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
                + ".signature"
            )

        d.validate_oidc(token(claims), self.config)
        for key, value in [
            ("repository_id", "123"),
            ("job_workflow_ref", "attacker/workflow@main"),
            ("event_name", "workflow_dispatch"),
            ("environment", "Preview"),
        ]:
            with self.subTest(key=key), self.assertRaises(d.DeliveryError):
                d.validate_oidc(token(claims | {key: value}), self.config)


class BigInJapanCompletion(VercelCompletion):
    config_id = "1325113680"


class ShelferCompletion(VercelCompletion):
    config_id = "1420482088"
