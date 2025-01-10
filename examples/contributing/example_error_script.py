# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openai",
# ]
# ///

import openai


def main():
    print("hello", openai.__version__)
    raise


if __name__ == "__main__":
    main()
