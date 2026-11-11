# Hermes Buildkite

Buildkite webhook ingress for Hermes Agent. Translates Buildkite's timestamped
HMAC header into Hermes Generic V2 headers without changing the signed body.
Hermes verifies authentication, rejects stale requests, deduplicates deliveries,
and owns agent admission, tool policy, execution and result delivery.

## Install and configure

Install `ParkesAI/hermes-buildkite` with the Hermes plugin manager, pinning the
commit with `--ref`. Configure a native `webhook` route with the same secret as
Buildkite's webhook token. Use **HMAC signature** mode in Buildkite. Never disable
authentication on the native route. Do not put secrets in this repository.

The plugin's `platforms.buildkite.extra` accepts `port` (8653), `upstream_port`
(8644), `route` (`buildkite`), and optional `profile`. The receiver always binds to
127.0.0.1. Expose only POST `/buildkite` through an HTTPS ingress, never the native
Hermes server or dashboard. Enable the plugin and restart the owning gateway at
a safe maintenance boundary.

For a busy gateway, the same receiver can run separately:

```sh
python -m hermes_buildkite --route buildkite --profile coordinator
```

Use exactly one lifecycle owner: standalone service or enabled gateway plugin.
Stop the standalone service before enabling the platform in the gateway.

Configure a native route filter/transform script to select the desired pipeline,
branch, event and state. Buildkite payloads use `event`, which Hermes does not
recognize as its event-type field: leave native `events` empty and inspect the
signed payload's `event` in the script. Keep inbound data out of instructions;
render only validated identifiers into the agent prompt. Use `deliver: log` to
avoid chat notification noise.

## Security and verification

This adapter has no signing secret and cannot manufacture authenticated events.
It forwards only the original body, translated signature and timestamp, and a
body-derived delivery ID. Caller-supplied delivery IDs and other auth headers
are discarded. Body size is capped at 2 MiB, upstream calls time out after 20
seconds, redirects are disabled, and unavailable Hermes returns 503 for retry.
A 202 response means admission, not completed analysis. Hermes owns its delivery
retention policy; do not assume permanent exactly-once execution. Require the
coordinator to deduplicate recurring incidents using the existing work queue.

The native Hermes webhook service must stay private and use a real route secret.
Passing or irrelevant builds should return ignored without waking an agent.

Run tests with `python -m unittest discover -s tests -v` in an environment with
aiohttp. Tests exercise signature translation, body preservation, invalid/stale
signatures, missing authentication, body limits and upstream failures. A real
provider delivery must also be verified after deployment.
