# Verification

## Automated checks

The HTTP suite exercises raw-byte authentication, stale/future timestamp rejection,
allowlists, failure-only filtering, malformed payloads, body limits, retryable
upstream failures and forwarding identity. Keys and payloads are synthetic.

The adapter contract suite targets Hermes 0.23.0 and tests construction, connect,
duplicate connect, native V2 signature acceptance, disconnect, reconnect and bind
failure cleanup. CI checks Python 3.11–3.14, lint, formatting and wheel/sdist contents.

## Operational qualification

Deployment verification is recorded after the pinned release is installed.
HTTP admission is not evidence of a completed agent response. Existing gateway
work must remain uninterrupted; the standalone lifecycle option is supported for
that case. Only one lifecycle owner may bind the receiver port.

## Limits

The native Hermes gateway owns durable admission, duplicate suppression and tool
permissions. This plugin does not provide permanent exactly-once delivery or a
second queue. Repeated failures from different builds require incident-level
coordination downstream. The liveness endpoint does not prove upstream health.
