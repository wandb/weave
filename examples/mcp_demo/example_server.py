import os

import httpx
from dotenv import load_dotenv

# import weave
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from openai import OpenAI
from PIL import Image as PILImage
from pydantic import BaseModel

load_dotenv()

# # Initialize Weave for tracing
# weave_client = weave.init("mcp_example")
# print(f"Weave initialized: {weave_client}")

# Create an MCP server
mcp = FastMCP("Demo")


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


@mcp.resource("config://app")
def get_config() -> str:
    """Static configuration data"""
    return "App configuration here"


@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: str) -> str:
    """Dynamic user data"""
    return f"Profile data for user {user_id}"


@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m**2)


class StationNameResponse(BaseModel):
    station_name: str


@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.weather.gov/stations")
        get_stations = response.json()

    stations = get_stations["features"]
    stationid_names = {
        station["properties"]["name"]: station["id"] for station in stations
    }

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = openai_client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": f"You are given the following weather station names: \n{list(stationid_names.keys())}\n\nYour job is to return the exact station name from the list that is closest to the city of {city}",
            },
        ],
        response_format=StationNameResponse,
    )

    station_name = response.choices[0].message.parsed.station_name
    station_id = stationid_names[station_name]

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{station_id}/observations/latest")
        get_forecast = response.json()

    forecast = get_forecast["properties"]

    weather_report = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": f"You are given the following weather forecast: {forecast}\n\nYour job is to return a weather report for {city}.",
            }
        ],
    )
    return weather_report.choices[0].message.content


@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]


@mcp.tool()
def create_thumbnail() -> Image:
    """Create a thumbnail from an image"""
    img = PILImage.open("docs/docs/media/codegen/eval_trace.png")
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")


if __name__ == "__main__":
    # Initialize and run the server
    print("Starting MCP server...")
    mcp.run(transport="stdio")
