# Contributing

Keep changes focused on receiving Buildkite alerts through the native Hermes
webhook pipeline. Avoid private gateway internals, monkey-patches, automatic
permission expansion or a second agent execution/queue implementation.

1. Install dependencies with `uv sync --locked --dev`.
2. Add a failing HTTP or lifecycle regression for a behavior change. Prefer real
   local request boundaries to mocks of the code under test.
3. Run the checks in the README, including distribution verification.
4. For changes touching the platform adapter, run `hermes plugins doctor .` and
   qualify startup/shutdown with a supported Hermes installation. Record what
   was actually tested; an HTTP 202 is not a completed agent run.
5. Use synthetic fixtures and generated test keys. Do not submit a deployment
   configuration, live alert payload, private host address or personal metadata.
6. Update the changelog and documentation when behavior changes. Bump the package
   and manifest versions together for a release.

Contributions are licensed under the repository's MIT license. Report security
issues through the private process in SECURITY.md rather than a public issue.
