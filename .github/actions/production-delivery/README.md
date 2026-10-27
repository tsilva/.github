# Trusted production delivery

This component executes only from a reusable workflow pinned to a full commit SHA.
Its fixed `apps.json` maps immutable GitHub repository IDs to Infisical Production
vaults, exact allowlisted key names, and Vercel/Cloudflare destinations. There are
no caller inputs for source projects, key names, destinations, commands or runners.

The privileged job checks out only this shared repository at the revision in the
GitHub-issued `job_workflow_ref` claim. It never checks out app code, installs app
dependencies, restores app caches, uploads artifacts or outputs secret values.
The caller's `ci.yml` must pass on the exact latest main commit before synchronization.
The deployment helper rechecks that commit before writing and verifies the final
Vercel Production deployment is READY for that exact SHA.

## Call contract

The entry workflow must be `.github/workflows/production-delivery.yml` in an
approved repository, triggered by main pushes or `workflow_dispatch`. The caller
keeps its secret-scanning prerequisite and concurrency group. Its reusable job
grants `contents: read`, `actions: read`, and `id-token: write`, and passes only
`VERCEL_TOKEN` (plus `CLOUDFLARE_API_TOKEN` for Chatex). The shared job uses the
`Production` environment on a fresh GitHub-hosted Ubuntu runner.

Pin the reusable workflow to a reviewed 40-character SHA. Public callers require
a public shared repository. Private callers may use public shared workflows too.
Do not add app checkout, caller-controlled inputs, arbitrary scripts or dependency
installation to the trusted job.

## Infisical trust policy

The reader must require all of these signed OIDC claims server-side:

- `repository_owner_id`: `26742`
- `repository_id`: the 16 reviewed IDs in `apps.json`
- `ref`: `refs/heads/main`
- `workflow_ref`: the approved caller production-delivery paths on main
- `job_workflow_ref`: the shared workflow path at its reviewed full commit SHA
- subject: the approved owner's `Production` environment context
- issuer: `https://token.actions.githubusercontent.com`
- audience: `https://app.infisical.com`

Token lifetime is at most 900 seconds. Local checks additionally verify caller
name/ID, environment, exact SHA and event claims before login. The local JWT
parser does not replace Infisical's signature verification or trust policy.

The machine identity remains a shared reader across the 16 application vaults.
Isolation is enforced by the trusted job and server-side reusable-workflow pin,
not by pretending this is 16 separate Infisical identities. App jobs do not receive
its access token. Maintainers of this shared code, the Infisical administrator,
and an administrator of a hosted runner execution remain trusted.

Private credentials are written only to Production Secret variables. Explicit
public configuration uses Production Config variables. Require Separate Values
remains enabled; Preview and Development are never overwritten. The relay's own
credentials must be in a separate vault inaccessible to the application reader.

## Verify and maintain

Run `python3 -m unittest discover -s .github/actions/production-delivery -p 'test_*.py'`
and lint both workflow YAML files before publication. Never log provider response
bodies or dump the environment while debugging. Error messages are deliberately
sanitized.

For an update, publish and test the reviewed shared commit, temporarily allow both
old and new shared SHAs in Infisical, update caller pins, run a canary and then all
callers, and remove the old SHA. Never temporarily remove the `job_workflow_ref`
condition. Test that a normal app job and an unapproved shared revision cannot
exchange their GitHub tokens. Changes to `apps.json` require source/destination
review and the same pin rollout as any other trusted-code change.
