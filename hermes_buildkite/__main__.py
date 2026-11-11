"""Run the installed plugin without restarting an active Hermes gateway."""

from aiohttp import web
from .receiver import Settings, create_app


def main():
    from hermes_cli.config import read_user_config_raw

    config = read_user_config_raw()["platforms"]["buildkite"]
    settings = Settings.from_config(config["token"], config.get("extra", {}))
    web.run_app(
        create_app(settings),
        host="127.0.0.1",
        port=settings.port,
        access_log_format="%a %t %s %b %Tf",
    )


if __name__ == "__main__":
    main()
