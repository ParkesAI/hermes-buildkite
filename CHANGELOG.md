# Changelog

## 0.1.1

- Authenticate Buildkite HMAC signatures and reject timestamps outside five minutes.
- Allowlist pipeline UUIDs and branch names; admit only failed `build.finished` events.
- Support native Hermes platform lifecycle and a standalone entry point using the same configuration.
- Add HTTP boundary tests, real Hermes lifecycle qualification, distribution checks and CI.

## 0.1.0

- Initial signature-header translator. Superseded by 0.1.1; use the latest release.
