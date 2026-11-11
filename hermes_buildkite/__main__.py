"""Run the same receiver separately when the active gateway cannot restart."""
import argparse
from aiohttp import web
from .receiver import Settings, create_app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8653)
    parser.add_argument('--upstream-port', type=int, default=8644)
    parser.add_argument('--route', default='buildkite')
    parser.add_argument('--profile')
    args = parser.parse_args()
    settings = Settings(**vars(args))
    web.run_app(create_app(settings), host='127.0.0.1', port=settings.port,
                access_log_format='%a %t %s %b %Tf')

if __name__ == '__main__':
    main()
