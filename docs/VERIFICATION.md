# Verification

## Automated checks

The HTTP suite exercises raw-byte authentication, stale/future timestamp rejection,
allowlists, failure-only filtering, malformed payloads, body limits, retryable
upstream failures and forwarding identity. Keys and payloads are synthetic.

The adapter contract suite targets Hermes 0.23.0 and tests construction, connect,
duplicate connect, native V2 signature acceptance, disconnect, reconnect and bind
failure cleanup. CI checks Python 3.11–3.14, lint, formatting and wheel/sdist contents.

## Operational qualification

On 2026-11-11, all nine tests passed against the installed Hermes SDK. Public
CI passed on Python 3.11, 3.12, 3.13 and 3.14, including the separate pinned
Hermes 0.23.0 lifecycle job. Wheel and sdist checks passed.

The pinned plugin was installed through the plugin manager and run under the
standalone lifecycle to preserve active workers. An operator-signed replay of a
real failed build traversed the public HTTPS ingress, received HTTP 202 and
started a coordinator session. The session called Buildkite's failure-summary
and build-list tools. An authenticated ping returned ignored. This establishes
replay delivery and agent execution, not receipt of a new provider-generated
scheduled failure.

For multiplexed gateways using dynamic subscriptions, the route must be available
in both the ingress home and target profile home. The installed Hermes version
resolves the route again in the receiving profile while preparing durable
admission. Missing target-profile configuration caused `not_found` and HTTP 503;
registering the same route there through the native subscription API resolved it.
No core patch or authentication bypass was used.
HTTP admission is not evidence of a completed agent response. Existing gateway
work must remain uninterrupted; the standalone lifecycle option is supported for
that case. Only one lifecycle owner may bind the receiver port.

## Limits

The native Hermes gateway owns durable admission, duplicate suppression and tool
permissions. This plugin does not provide permanent exactly-once delivery or a
second queue. Repeated failures from different builds require incident-level
coordination downstream. The liveness endpoint does not prove upstream health.
