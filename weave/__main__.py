import argparse
import time
from weave import server


def start_ui() -> None:
    print("Starting server...")
    serv = server.HttpServer(port=3000)  # type: ignore
    serv.start()
    print("Server started")
    print("http://localhost:3000/browse2")
    while True:
        time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weave Command Line Tool")
    subparsers = parser.add_subparsers(dest="command")

    ui_parser = subparsers.add_parser("ui")

    args = parser.parse_args()

    if args.command == "ui":
        start_ui()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
