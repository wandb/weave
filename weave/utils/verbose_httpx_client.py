import json
from datetime import datetime
from typing import Any

import httpx
from weave_trace import DefaultHttpxClient


class VerboseClient(DefaultHttpxClient):
    def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        # Print request details
        print("\n=== Request ===")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        # print("Headers:")
        # for name, value in request.headers.items():
        #     print(f"  {name}: {value}")

        if request.content:
            try:
                # Try to parse and print JSON content
                body = json.loads(request.content)
                print("Body (JSON):")
                print(json.dumps(body, indent=2))
            except json.JSONDecodeError:
                # If not JSON, print raw content
                print("Body:")
                print(request.content.decode())

        print("===============")

        # Send the actual request
        response = super().send(request, **kwargs)

        # Print response details
        print("\n=== Response ===")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Status: {response.status_code} {response.reason_phrase}")
        # print("Headers:")
        # for name, value in response.headers.items():
        #     print(f"  {name}: {value}")

        try:
            # Try to parse and print JSON content
            body = response.json()
            print("Body (JSON):")
            print(json.dumps(body, indent=2))
        except (json.JSONDecodeError, ValueError):
            # If not JSON, print raw content
            print("Body:")
            print(response.text)

        print("===============")

        return response
