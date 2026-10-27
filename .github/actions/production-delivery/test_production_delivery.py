"""Fail-closed delivery tests; all external requests are mocked."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "delivery", Path(__file__).with_name("production_delivery.py")
)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        oidc = patch.object(d, "validate_oidc")
        oidc.start()
        self.addCleanup(oidc.stop)
        self.config = {
            "repository": "tsilva/example",
            "secretNames": ["SENTRY_AUTH_TOKEN"],
            "configNames": [],
            "infisicalProjectId": "vault",
            "identityId": "reader",
            "vercelProjectId": "prj_example",
            "vercelTeamId": "team_example",
            "githubRepositoryId": 123,
            "workerName": "example",
            "cloudflareAccountId": "account",
        }
        self.sha = "a" * 40
        self.env = {
            "GITHUB_REPOSITORY": "tsilva/example",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_SHA": self.sha,
            "GITHUB_WORKFLOW_REF": "tsilva/example/.github/workflows/production-delivery.yml@refs/heads/main",
            "GH_TOKEN": "fake-github",
            "VERCEL_TOKEN": "fake-vercel",
            "CLOUDFLARE_API_TOKEN": "fake-cloudflare",
        }

    def test_fork_branch_event_and_workflow_fail_before_network(self):
        cases = {
            "GITHUB_REPOSITORY": "attacker/example",
            "GITHUB_REF": "refs/heads/feature",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_WORKFLOW_REF": "tsilva/example/.github/workflows/other.yml@refs/heads/main",
        }
        for key, value in cases.items():
            with (
                self.subTest(key=key),
                patch.dict(os.environ, self.env | {key: value}, clear=True),
                patch.object(d, "request") as request,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.context(self.config)
                request.assert_not_called()

    def test_old_commit_cannot_mutate(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(d, "request", return_value={"object": {"sha": "b" * 40}}),
        ):
            with self.assertRaises(d.DeliveryError):
                d.context(self.config)

    def test_malformed_sha_cannot_mutate(self):
        with (
            patch.dict(os.environ, self.env | {"GITHUB_SHA": "main"}, clear=True),
            patch.object(d, "request") as request,
        ):
            with self.assertRaises(d.DeliveryError):
                d.context(self.config)
            request.assert_not_called()

    def test_duplicate_and_combined_targets_fail_closed(self):
        for items in [
            [{"key": "K", "target": ["production", "preview"]}],
            [{"key": "K", "target": ["production"]}] * 2,
            [{"key": "K", "target": ["production"], "gitBranch": "feature"}],
        ]:
            with self.subTest(items=items), self.assertRaises(d.DeliveryError):
                d.production_matches(items, "K")

    def test_preview_credentials_are_preserved(self):
        production = {"key": "K", "target": ["production"]}
        self.assertEqual(
            d.production_matches(
                [production, {"key": "K", "target": ["preview"]}], "K"
            ),
            [production],
        )

    def test_wrong_vercel_project_team_and_repo_fail_before_write(self):
        good = {
            "id": "prj_example",
            "accountId": "team_example",
            "link": {"repoId": "123"},
        }
        for bad in [
            good | {"id": "other"},
            good | {"accountId": "other"},
            good | {"link": {"repoId": "456"}},
        ]:
            with (
                self.subTest(bad=bad),
                patch.object(d, "vercel_request", return_value=bad) as request,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.sync_vercel(self.config, {"SENTRY_AUTH_TOKEN": "fake-secret"})
                self.assertEqual(
                    [call.args[1] for call in request.call_args_list], ["GET"]
                )

    def test_missing_worker_binding_prevents_write(self):
        with patch.object(d, "cloudflare_request", return_value=[]) as request:
            with self.assertRaises(d.DeliveryError):
                d.sync_worker(self.config, "fake-secret")
            self.assertEqual([call.args[1] for call in request.call_args_list], ["GET"])

    def test_ready_build_without_domain_assignment_is_not_live(self):
        for assigned in [None, False, 0, "false", "true"]:
            with self.subTest(assigned=assigned):
                self.assertFalse(d.production_aliases_assigned(
                    {"readyState": "READY", "aliasAssigned": assigned}
                ))
        for assigned in [True, 1792788551754]:
            with self.subTest(assigned=assigned):
                self.assertTrue(d.production_aliases_assigned(
                    {"readyState": "READY", "aliasAssigned": assigned}
                ))

    def test_domain_assignment_error_holds_delivery(self):
        with self.assertRaises(d.DeliveryError):
            d.production_aliases_assigned({
                "readyState": "READY", "aliasAssigned": True,
                "aliasError": {"code": "check_failed", "message": "private provider detail"},
            })

    def test_deploy_waits_for_production_assignment_after_ready_build(self):
        import contextlib
        import io

        ready = {
            "projectId": "prj_example", "target": "production",
            "readyState": "READY", "meta": {"githubCommitSha": self.sha},
        }
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"GITHUB_RUN_ID": "1"}),
            patch.object(d, "wait_for_ci"),
            patch.object(d, "context") as context,
            patch.object(d, "verify_vercel"),
            patch.object(d, "vercel_request", side_effect=[
                {"id": "dpl_example"}, ready | {"aliasAssigned": False},
                ready | {"aliasAssigned": True},
            ]) as request,
            patch.object(d.time, "sleep") as sleep,
            contextlib.redirect_stdout(output),
        ):
            d.deploy_vercel(self.config | {"vercelProjectName": "example"}, self.sha)
        sleep.assert_called_once_with(15)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(context.call_count, 2)
        self.assertEqual(output.getvalue().count("Production READY:"), 1)

    def test_failed_ci_prevents_deployment(self):
        with (
            patch.object(d, "wait_for_ci", side_effect=d.DeliveryError("CI failed")),
            patch.object(d, "vercel_request") as request,
        ):
            with self.assertRaises(d.DeliveryError):
                d.deploy_vercel(self.config, self.sha)
            request.assert_not_called()

    def test_untrusted_oidc_endpoint_is_rejected(self):
        with (
            patch.dict(
                os.environ,
                {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://attacker.example/token"},
                clear=True,
            ),
            patch.object(d, "request") as request,
        ):
            with self.assertRaises(d.DeliveryError):
                d.infisical_secrets(self.config)
            request.assert_not_called()

    def test_source_metadata_and_allowlist_are_enforced(self):
        env = {
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token?api=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "fake",
        }
        secret = {
            "secretKey": "SENTRY_AUTH_TOKEN",
            "workspace": "vault",
            "environment": "prod",
            "type": "shared",
            "secretValue": "fake-secret",
            "version": 3,
        }
        for wrong in [
            secret | {"workspace": "other"},
            secret | {"environment": "dev"},
            secret | {"secretValue": ""},
            secret | {"secretKey": "OTHER"},
        ]:
            with (
                self.subTest(wrong=wrong),
                patch.dict(os.environ, env, clear=True),
                patch.object(d, "mask"),
                patch.object(
                    d,
                    "request",
                    side_effect=[
                        {"value": "fake-jwt"},
                        {"accessToken": "fake-access"},
                        {"secret": wrong},
                    ],
                ) as request,
            ):
                with self.assertRaises(d.DeliveryError):
                    d.infisical_secrets(self.config)
                self.assertIn(
                    "includeImports=false", request.call_args_list[-1].args[1]
                )
                self.assertIn(
                    "expandSecretReferences=false", request.call_args_list[-1].args[1]
                )

    def test_empty_source_needs_no_identity_or_network(self):
        with patch.object(d, "request") as req:
            self.assertEqual(d.infisical_secrets({"secretNames": []}), {})
            req.assert_not_called()

    def test_missing_source_names_the_key_without_exposing_provider_details(self):
        env = {
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "fake-oidc-credential",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(d, "mask"),
            patch.object(
                d,
                "request",
                side_effect=[
                    {"value": "fake-jwt"},
                    {"accessToken": "fake-access-token"},
                    d.ProviderHTTPError(404),
                ],
            ),
        ):
            with self.assertRaisesRegex(
                d.DeliveryError, "SENTRY_AUTH_TOKEN.*HTTP 404"
            ) as error:
                d.infisical_secrets(self.config)
        for private_value in ("fake-jwt", "fake-access-token", "fake-oidc-credential"):
            self.assertNotIn(private_value, str(error.exception))

    def test_http_error_does_not_expose_the_response_body_or_url(self):
        from io import BytesIO
        from urllib.error import HTTPError

        error = HTTPError(
            "https://provider.invalid/private",
            404,
            "private reason",
            {},
            BytesIO(b"private response"),
        )
        with patch.object(d.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(d.ProviderHTTPError) as raised:
                d.request("GET", "https://provider.invalid/private", "private-token")
        self.assertEqual(raised.exception.status, 404)
        self.assertNotIn("private", str(raised.exception))

    def test_all_targets_are_checked_before_first_write(self):
        envs = [{"key": "SECOND", "target": ["production", "preview"]}]
        with (
            patch.object(d, "verify_vercel"),
            patch.object(d, "vercel_request", return_value={"envs": envs}) as req,
        ):
            with self.assertRaises(d.DeliveryError):
                d.sync_vercel(
                    self.config | {"secretNames": ["FIRST", "SECOND"]},
                    {"FIRST": "fake-a", "SECOND": "fake-b"},
                )
            self.assertEqual([call.args[1] for call in req.call_args_list], ["GET"])

    def test_multiple_keys_use_one_oidc_session(self):
        env = {
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "fake",
        }

        def secret(name):
            return {
                "secret": {
                    "secretKey": name,
                    "workspace": "vault",
                    "environment": "prod",
                    "type": "shared",
                    "secretValue": "fake-" + name,
                }
            }

        config = self.config | {"secretNames": ["FIRST", "SECOND"]}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(d, "mask"),
            patch.object(
                d,
                "request",
                side_effect=[
                    {"value": "fake-jwt"},
                    {"accessToken": "fake-access"},
                    secret("FIRST"),
                    secret("SECOND"),
                ],
            ) as req,
        ):
            self.assertEqual(
                d.infisical_secrets(config),
                {"FIRST": "fake-FIRST", "SECOND": "fake-SECOND"},
            )
            self.assertEqual(
                sum(call.args[0] == "POST" for call in req.call_args_list), 1
            )

    def test_missing_source_stops_before_any_provider_write(self):
        with (
            patch.object(
                d, "configuration", return_value=self.config | {"destination": "vercel"}
            ),
            patch.object(d, "context", return_value=self.sha),
            patch.object(d, "wait_for_ci"),
            patch.object(
                d, "infisical_secrets", side_effect=d.DeliveryError("Missing key")
            ),
            patch.object(d, "sync_vercel") as sync,
            patch.object(d.sys, "argv", ["delivery", "sync"]),
        ):
            with self.assertRaises(d.DeliveryError):
                d.main()
            sync.assert_not_called()

    def test_secret_update_addresses_only_production_id(self):
        key = "SENTRY_AUTH_TOKEN"
        prod = {
            "key": key,
            "id": "prod-id",
            "target": ["production"],
            "type": "sensitive",
            "visibility": "secret",
        }
        preview = prod | {"id": "preview-id", "target": ["preview"]}
        with (
            patch.object(d, "verify_vercel"),
            patch.object(
                d,
                "vercel_request",
                side_effect=[
                    {"envs": [prod, preview]},
                    prod,
                    {"envs": [prod, preview]},
                ],
            ) as req,
        ):
            d.sync_vercel(self.config, {key: "fake-secret"})
            call = req.call_args_list[1]
            self.assertEqual(call.args[1], "PATCH")
            self.assertTrue(call.args[2].endswith("/prod-id"))
            self.assertNotIn("key", call.args[3])
            self.assertNotIn("target", call.args[3])
            self.assertEqual(call.args[3]["visibility"], "secret")

    def test_config_migration_preserves_preview(self):
        key = "SENTRY_DSN"
        config = self.config | {"secretNames": [key], "configNames": [key]}
        old = {
            "key": key,
            "id": "old-prod",
            "target": ["production"],
            "type": "sensitive",
        }
        preview = old | {"id": "preview-id", "target": ["preview"]}
        new = old | {"id": "new-prod", "type": "encrypted", "visibility": "config"}
        with (
            patch.object(d, "verify_vercel"),
            patch.object(
                d,
                "vercel_request",
                side_effect=[
                    {"envs": [old, preview]},
                    {},
                    {"created": new, "failed": []},
                    {"envs": [new, preview]},
                ],
            ) as req,
        ):
            d.sync_vercel(config, {key: "https://public.example"})
            self.assertEqual(
                [c.args[1] for c in req.call_args_list],
                ["GET", "DELETE", "POST", "GET"],
            )
            self.assertTrue(req.call_args_list[1].args[2].endswith("/old-prod"))
            self.assertEqual(req.call_args_list[2].args[3]["target"], ["production"])
            self.assertEqual(req.call_args_list[2].args[3]["visibility"], "config")

    def test_auth_token_cannot_be_classified_as_config(self):
        with patch.object(d, "vercel_request") as req:
            with self.assertRaises(d.DeliveryError):
                d.sync_vercel(
                    self.config | {"configNames": ["SENTRY_AUTH_TOKEN"]},
                    {"SENTRY_AUTH_TOKEN": "private"},
                )
            req.assert_not_called()

    def test_combined_target_migration_fails_before_delete(self):
        key = "SENTRY_DSN"
        config = self.config | {"secretNames": [key], "configNames": [key]}
        row = {
            "key": key,
            "id": "shared",
            "target": ["production", "preview"],
            "type": "sensitive",
        }
        with (
            patch.object(d, "verify_vercel"),
            patch.object(d, "vercel_request", return_value={"envs": [row]}) as req,
        ):
            with self.assertRaises(d.DeliveryError):
                d.sync_vercel(config, {key: "public"})
            self.assertEqual([c.args[1] for c in req.call_args_list], ["GET"])

    def test_provider_error_never_exposes_body_or_value(self):
        with self.assertRaises(d.DeliveryError) as error:
            d.confirmed_variable(
                {
                    "failed": [
                        {"error": {"message": "private-value", "code": "private-value"}}
                    ]
                },
                "SENTRY_AUTH_TOKEN",
            )
        self.assertIn("SENTRY_AUTH_TOKEN", str(error.exception))
        self.assertNotIn("private-value", str(error.exception))

    def test_create_accepts_object_or_single_element_list(self):
        row = {"key": "K", "id": "prod-id"}
        for created in (row, [row]):
            self.assertEqual(
                d.confirmed_variable({"created": created, "failed": []}, "K"), row
            )
        for created in ([], [row, row], {"key": "wrong"}):
            with self.assertRaises(d.DeliveryError):
                d.confirmed_variable({"created": created}, "K")

    def test_missing_source_prevents_writes(self):
        with patch.object(d, "vercel_request") as req:
            with self.assertRaises(d.DeliveryError):
                d.sync_vercel(self.config, {})
            req.assert_not_called()





class SharedBoundaryTests(unittest.TestCase):
    def setUp(self):
        import json
        self.apps = json.loads(Path(__file__).with_name("apps.json").read_text())
        self.config = self.apps["1253290016"]
        self.revision = "b" * 40
        self.env = {
            "GITHUB_REPOSITORY_ID": "1253290016",
            "GITHUB_REPOSITORY_OWNER_ID": "26742",
            "GITHUB_REPOSITORY": "tsilva/modelarchviz",
            "GITHUB_SHA": "a" * 40,
            "SHARED_DELIVERY_REVISION": self.revision,
        }

    def test_only_fixed_immutable_repository_ids_can_select_a_vault(self):
        for changes in [
            {"GITHUB_REPOSITORY_ID": "999"},
            {"GITHUB_REPOSITORY_OWNER_ID": "999"},
            {"GITHUB_REPOSITORY": "tsilva/shelfer"},
            {"SHARED_DELIVERY_REVISION": "main"},
        ]:
            with self.subTest(changes=changes), patch.dict(os.environ, self.env | changes, clear=True):
                with self.assertRaises(d.DeliveryError):
                    d.configuration()
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(d.configuration(), self.config)

    def claims(self):
        return {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": d.INFISICAL,
            "repository": "tsilva/modelarchviz", "repository_id": "1253290016",
            "repository_owner_id": "26742", "ref": "refs/heads/main",
            "sha": "a" * 40, "environment": "Production",
            "workflow_ref": "tsilva/modelarchviz/.github/workflows/production-delivery.yml@refs/heads/main",
            "job_workflow_ref": "tsilva/.github/.github/workflows/production-delivery.yml@" + self.revision,
            "event_name": "workflow_dispatch", "iat": d.time.time(), "exp": d.time.time() + 300,
        }

    def jwt(self, claims):
        import json, base64
        return "header." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".signature"

    def test_oidc_requires_the_pinned_callee_and_exact_caller(self):
        claims = self.claims()
        wrong = {
            "job_workflow_ref": "tsilva/.github/.github/workflows/production-delivery.yml@refs/heads/main",
            "repository_id": "1420482088", "repository_owner_id": "123",
            "sha": "c" * 40, "environment": "Preview", "ref": "refs/heads/pull/1",
            "aud": "other", "event_name": "pull_request", "exp": d.time.time() - 1,
        }
        with patch.dict(os.environ, self.env, clear=True):
            d.validate_oidc(self.jwt(claims), self.config)
            for key, value in wrong.items():
                with self.subTest(key=key), self.assertRaises(d.DeliveryError):
                    d.validate_oidc(self.jwt(claims | {key: value}), self.config)
            with self.assertRaises(d.DeliveryError):
                d.validate_oidc(self.jwt({k:v for k,v in claims.items() if k != "job_workflow_ref"}), self.config)

    def test_wrong_oidc_never_reaches_infisical_login(self):
        env = self.env | {
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.actions.githubusercontent.com/token",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "fake",
        }
        claims = self.claims() | {"job_workflow_ref": "untrusted"}
        with patch.dict(os.environ, env, clear=True), patch.object(d, "mask"), patch.object(d, "request", return_value={"value": self.jwt(claims)}) as request:
            with self.assertRaises(d.DeliveryError):
                d.infisical_secrets(self.config)
            self.assertEqual(request.call_count, 1)

    def test_reshoot_realtime_keeps_the_sealing_key_private(self):
        app = self.apps["1317499522"]
        self.assertEqual(app["repository"], "tsilva/reshoot")
        self.assertEqual(app["infisicalProjectId"], "05231e99-a5e4-4d81-bbae-ea17a054ae54")
        self.assertEqual(app["vercelProjectId"], "prj_L1D4dlxsUv8zZORHmxEmDZnE3lCV")
        self.assertTrue({"NEON_REALTIME_URL", "NEON_REALTIME_SECRET"} <= set(app["secretNames"]))
        self.assertIn("NEON_REALTIME_URL", d.config_names(app))
        self.assertNotIn("NEON_REALTIME_SECRET", d.config_names(app))
        with self.assertRaises(d.DeliveryError):
            d.config_names(app | {"configNames": app["configNames"] + ["NEON_REALTIME_SECRET"]})
        for other in self.apps.values():
            if other["repository"] != "tsilva/reshoot":
                self.assertFalse({"NEON_REALTIME_URL", "NEON_REALTIME_SECRET"} & set(other["secretNames"]))

    def test_mapping_has_eighteen_separate_fixed_sources_and_destinations(self):
        self.assertEqual(len(self.apps), 18)
        self.assertEqual(len({v["infisicalProjectId"] for v in self.apps.values()}), 18)
        self.assertEqual(len({v["vercelProjectId"] for v in self.apps.values()}), 18)
        self.assertFalse({"GITHUB_PRODUCTION_DISPATCH_TOKEN", "INFISICAL_WEBHOOK_SIGNING_KEYS"} & set(self.config["secretNames"]))
        for key, app in self.apps.items():
            self.assertEqual(key, str(app["githubRepositoryId"]))
            self.assertTrue(set(app.get("configNames", [])) <= set(app["secretNames"]))

if __name__ == "__main__":
    unittest.main()
