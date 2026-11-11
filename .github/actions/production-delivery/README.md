# Trusted production delivery

This component executes only from a reusable workflow pinned to a full commit SHA.
Its fixed `apps.json` maps immutable GitHub repository IDs to Infisical Production
vaults, exact allowlisted key names, and Vercel/Cloudflare destinations. There are
no caller inputs for source projects, key names, destinations, commands or runners.

The privileged job checks out only this shared repository at the revision in the
GitHub-issued `job_workflow_ref` claim. It never checks out app code, installs app
dependencies, restores app caches, uploads artifacts or outputs secret values.
The caller's `ci.yml`, named `CI`, must pass on the exact latest main commit before synchronization.
The deployment helper rechecks that commit before writing and verifies the final
Vercel Production deployment is READY for that exact SHA. TubeScribe performs
the final verification in a separate completion-event job, as described below.

## Call contract

The entry workflow must be `.github/workflows/production-delivery.yml` in an
approved repository, triggered by successful `workflow_run` completion of main-push
`CI` or by `workflow_dispatch`. Automatic callers use `workflows: [CI]`,
`types: [completed]` and `branches: [main]`; they do not start delivery on `push`.
Every job is gated before runner allocation on a successful push CI from the same
immutable repository, the `ci.yml` path and the delivery run's exact SHA. The caller
keeps its secret-scanning prerequisite and concurrency group. Its reusable job
grants `contents: read`, `actions: read`, and `id-token: write`, and passes only
`VERCEL_TOKEN` (plus `CLOUDFLARE_API_TOKEN` for Chatex). The shared job uses the
`Production` environment on a fresh GitHub-hosted Ubuntu runner.

The helper checks the event's repository IDs, workflow path, main branch, success,
run ID and attempt against GitHub's current CI metadata. `workflow_run` uses the
default-branch tip as `GITHUB_SHA`; a CI event for a different SHA is rejected,
and the SHA must still be the current head of main before writes. A newer run or
rerun attempt supersedes the old event. Manual/relay dispatches require the latest
main-push CI for that same SHA to have already succeeded. Pending or failed CI
fails immediately, without polling or retrieving application secrets.

Callers that build on GitHub can set `sync_only: true`. The shared job still
checks the exact commit and syncs its fixed Production allowlist. A separate
caller job must depend on that job, verify the prebuilt deployment and promote
it. That job receives no Infisical reader credentials.

Pin the reusable workflow to a reviewed 40-character SHA. Public callers require
a public shared repository. Private callers may use public shared workflows too.
Do not add app checkout, caller-controlled inputs, arbitrary scripts or dependency
installation to the trusted job.

## Event-driven Vercel completion

Only TubeScribe's immutable repository ID is enabled in the pinned map. Other
callers retain synchronous verification and their existing `sync_only` contract.
No caller input selects an event mode, runner, vault, project, domain or command.

After successful main-push CI (or an authorized manual/relay dispatch), the same
trusted job validates GitHub OIDC, syncs the allowlisted Production keys, then
submits the exact SHA to Vercel. Deployment metadata binds the submission to its
initiating run ID/attempt, shared implementation SHA, and successful CI run
ID/attempt. The job ends without polling. Its success confirms submission only.
For this phase, `environment.deployment: false` keeps Production secrets, branch
restrictions, required reviewers and wait timers, but avoids a premature green
GitHub deployment record. The final verification job creates that record.
Custom deployment-protection apps are incompatible with GitHub's opt-out and
fail closed; do not remove those protections to enable this path.

The caller also accepts Vercel's `vercel.deployment.success`, `.error`, `.canceled`
and `.failed` repository dispatches, including `.ignored` and `.skipped`
cancellations. A successful event means Vercel has built
and automatically promoted the deployment; `deployment.ready` is deliberately
not accepted. Both workflow conditions and the helper require Vercel's immutable
bot ID, TubeScribe's immutable repository/project IDs, Production, and the exact
current main SHA. The event URL and claimed aliases are never fetched or trusted.

Completion validates the protected job's GitHub-issued OIDC identity but does
not exchange it with Infisical, read app keys, synchronize variables or deploy.
It independently rechecks GitHub's latest exact-commit CI; Vercel's project,
team, repository link, READY state and successful domain assignment; the stored
receipt; and the original caller run, attempt and pinned reusable workflow.
Failed, cancelled, replaced or retried initiators are rejected. A callback may
arrive while the initiating run is finishing cleanup: an in-progress original
run is permitted only with the same verified receipt and trusted callee pin.
Finally, the pinned Production hostname must currently point to that exact
deployment ID. Superseded commits and deployments cannot be reported verified.

Completion has a separate concurrency group so callbacks cannot displace queued
deployment submissions. Repeated callbacks are read-only. Failure events never
report READY. There is no scheduled polling or build-wait sleep. The optional
`verify_deployment_id` input supports a one-shot, read-only `workflow_dispatch`
recheck; an empty input retains ordinary deployment behavior. A lost completion
event therefore requires explicit recovery rather than an assumed success.

These short, standard-library-only TubeScribe jobs use the fixed `ubuntu-slim`
runner mapping and a 14-minute timeout. Other callers keep `ubuntu-24.04` and
their existing timeout. No runner is supplied by callers. Completion adds a
separate job, so savings depend on build duration and per-job billing rounding;
using the lightweight runner limits that overhead.

Enabling the reviewed revision requires appending its exact `job_workflow_ref`
pin to the existing Infisical policy before updating TubeScribe. Preserve all
old pins, claim restrictions, grants and token lifetimes. Completion does not
need an additional identity, service credential, webhook service or GitHub App.

## Infisical trust policy

The reader must require all of these signed OIDC claims server-side:

- `repository_owner_id`: `26742`
- `repository_id`: the 17 reviewed IDs in `apps.json`
- `ref`: `refs/heads/main`
- `workflow_ref`: the approved caller production-delivery paths on main
- `job_workflow_ref`: the shared workflow path at its reviewed full commit SHA
- subject: the approved owner's `Production` environment context
- issuer: `https://token.actions.githubusercontent.com`
- audience: `https://app.infisical.com`

Token lifetime is at most 900 seconds. Local checks additionally verify caller
name/ID, environment, exact SHA and the actual `workflow_run` or
`workflow_dispatch` event claim before login. The local JWT
parser does not replace Infisical's signature verification or trust policy.

The published map includes 17 application vaults. The machine identity uses
shared reader grants; isolation depends on the trusted job and server-side
reusable-workflow pin. Retiring a mapping also requires separately reconciling
reader grants and OIDC policy: a map edit cannot revoke access or change an
already pinned revision. App jobs do not receive its access token. Maintainers of this shared code, the Infisical administrator,
and an administrator of a hosted runner execution remain trusted.

Private credentials are written only to Production Secret variables. Explicit
public configuration uses Production Config variables. Require Separate Values
remains enabled; Preview and Development are never overwritten. The relay's own
credentials must be in a separate vault inaccessible to the application reader.

Reshoot's allowlist includes its Production `NEON_REALTIME_URL` as public
configuration and `NEON_REALTIME_SECRET` as a private Secret. These values come
only from Reshoot's isolated Production vault; no other app's allowlist changes.
Its `RESHOOT_PAYMENTS_MODE` and four `STRIPE_TEST_*` monthly Price/portal object
IDs are public configuration from that vault. `STRIPE_TEST_SECRET_KEY` and
`STRIPE_TEST_WEBHOOK_SECRET` remain private Production Secrets. These settings
support sandbox subscriptions only; live billing is disabled by the application.

Reshoot's native Clerk/Vercel integration owns `CLERK_SECRET_KEY` and
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`. They are an explicitly approved exception to
the Infisical source policy and are excluded from this sync. The integration
supplies distinct Production and Preview keys; delivery must not overwrite them.

## Verify and maintain

Run `python3 -m unittest discover -s .github/actions/production-delivery -p 'test_*.py'`
and lint both workflow YAML files before publication. Never log provider response
bodies or dump the environment while debugging. Error messages are deliberately
sanitized.

For an update, publish and test the reviewed shared commit, append the new exact
shared SHA in Infisical while retaining previous pins, then update the selected
caller's trigger and pin together and verify a canary. Old-pin removal requires
separate authorization after reviewing the corresponding live callers. Never
temporarily remove the `job_workflow_ref`
condition. Test that a normal app job and an unapproved shared revision cannot
exchange their GitHub tokens. Changes to `apps.json` require source/destination
review and the same pin rollout as any other trusted-code change.

If the reader additionally binds `event_name`, allow `workflow_run` and
`workflow_dispatch` while preserving all other claims. Keep old pins authorized
until every live caller has moved; archived disabled callers remain disabled.
Existing prebuilt and Worker delivery jobs keep their dependency ordering and
receive no Infisical reader access. CI caches and artifacts are never consumed
by the trusted credential job.
