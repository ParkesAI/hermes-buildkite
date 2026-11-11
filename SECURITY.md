# Security policy

## Reporting

Use GitHub's **Report a vulnerability** feature on this repository. Do not post
live signing secrets, personal alert data, provider tokens or exploit details in
public issues. Private vulnerability reporting must be enabled by the maintainer
before this route can be used; if unavailable, open an issue requesting a private
contact without including the sensitive details.

## Trust boundaries

The adapter runs as in-process Python inside Hermes; it is not a sandbox. Review
the code and pin the installation to a reviewed immutable commit. Installation
does not grant the agent any additional tools.

The public-facing boundary is your HTTPS ingress. Publish only `POST /buildkite`,
preserve raw request bytes, restrict request size and apply appropriate rate
limits. The plugin itself binds only to loopback and authenticates every inbound
request before decoding JSON. It refuses redirects from its fixed loopback
upstream. Local processes with the same operating-system account remain inside
the trust boundary; loopback is not protection against a compromised host.

The plugin checks Buildkite's timestamped HMAC-SHA256 signature using constant-time comparison and rejects timestamps more than five minutes in the past or future.
An allowlist restricts pipeline UUIDs and branches. Valid signing does not make build messages,
stack traces or other alert text trusted instructions. Keep the native webhook
agent's permissions narrow and review downstream model/data retention settings.

Duplicate identity is derived from the signed body, not a mutable request header.
The native Hermes receiver owns duplicate suppression and retention. Buildkite may re-sign retries with a fresh dispatch timestamp. Incident-level
deduplication still belongs in the coordinator/work queue. Configure and verify
longer retention in Hermes if required.

Never commit deployment configuration or real secrets. Store the webhook
signing token only in the protected local Hermes configuration. It appears in
both the platform token and native route signing configuration. Rotate both
together when rotating the Buildkite webhook token. Protect backups as well.

## Supported versions

Security fixes target the most recent released plugin version. See
[verification](docs/VERIFICATION.md) for the qualified Hermes version and
remaining coverage limitations.
