"""Executable entry point for the service and cron registration."""

import argparse

import uvicorn

from reminder_service import install_scan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-scan", metavar="PUBLIC_URL")
    args = parser.parse_args()
    if args.install_scan:
        print(f"scheduled: {install_scan(args.install_scan)}")
        return
    uvicorn.run("reminder_service:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
