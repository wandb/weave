import argparse
import time
from weave import server


def start_ui() -> None:
    serv = server.HttpServer(port=3000)  # type: ignore
    serv.start()
    print("http://localhost:3000/browse2")
    while True:
        time.sleep(10)


def serve_model(model_uri: str) -> None:
    print("SERVE MODEL", model_uri)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weave Command Line Tool")
    subparsers = parser.add_subparsers(dest="command")

    ui_parser = subparsers.add_parser("ui")
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument(
        "--model", type=str, required=True, help="URI to the model"
    )

    args = parser.parse_args()

    if args.command == "ui":
        start_ui()
    elif args.command == "serve":
        serve_model(args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
