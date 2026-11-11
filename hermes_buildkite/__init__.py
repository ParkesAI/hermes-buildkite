"""Buildkite signature translation for native Hermes webhooks."""


def register(ctx):
    from .adapter import BuildkiteAdapter

    ctx.register_platform(
        name="buildkite",
        label="Buildkite webhooks",
        adapter_factory=BuildkiteAdapter,
        check_fn=lambda: True,
        install_hint="Configure a native webhook route with the Buildkite signing token",
        dashboard_description="Receive signed Buildkite events through native Hermes authentication",
        emoji="🪁",
    )
