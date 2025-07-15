"""Example usage of the async Weave client."""

import asyncio
from typing import Any, Optional

from weave.trace.async_client import AsyncWeaveClient, async_op, create_async_client


# Example 1: Basic async operations
@async_op(name="fetch_data", display_name="Fetch External Data")
async def fetch_data(url: str, timeout: float = 5.0) -> dict[str, Any]:
    """Simulate fetching data from an external API."""
    await asyncio.sleep(0.5)  # Simulate network delay
    return {
        "url": url,
        "data": {"temperature": 72.5, "humidity": 65},
        "timestamp": "2024-01-15T10:30:00Z",
    }


@async_op(name="process_data")
async def process_data(data: dict[str, Any]) -> dict[str, Any]:
    """Process the fetched data."""
    await asyncio.sleep(0.2)  # Simulate processing time
    
    # Extract and transform data
    result = {
        "temperature_fahrenheit": data["data"]["temperature"],
        "temperature_celsius": (data["data"]["temperature"] - 32) * 5/9,
        "humidity_percent": data["data"]["humidity"],
        "comfort_level": "comfortable" if 68 <= data["data"]["temperature"] <= 76 else "uncomfortable",
    }
    return result


@async_op(
    name="analyze_batch",
    call_display_name=lambda inputs: f"Analyze {len(inputs['items'])} items"
)
async def analyze_batch(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a batch of items concurrently."""
    # Process items concurrently
    tasks = [process_data(item) for item in items]
    results = await asyncio.gather(*tasks)
    
    # Aggregate results
    avg_temp = sum(r["temperature_fahrenheit"] for r in results) / len(results)
    avg_humidity = sum(r["humidity_percent"] for r in results) / len(results)
    
    return {
        "total_items": len(items),
        "average_temperature": avg_temp,
        "average_humidity": avg_humidity,
        "results": results,
    }


# Example 2: Class-based async operations
class AsyncWeatherService:
    """Example service using async operations."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo-key"
    
    @async_op(name="weather_service.get_current")
    async def get_current_weather(self, city: str) -> dict[str, Any]:
        """Get current weather for a city."""
        # Simulate API call
        await asyncio.sleep(0.3)
        
        return {
            "city": city,
            "temperature": 75.2,
            "humidity": 60,
            "conditions": "partly cloudy",
            "wind_speed": 12.5,
        }
    
    @async_op(name="weather_service.get_forecast")
    async def get_forecast(self, city: str, days: int = 5) -> list[dict[str, Any]]:
        """Get weather forecast."""
        # Simulate fetching forecast data
        await asyncio.sleep(0.5)
        
        forecast = []
        for i in range(days):
            forecast.append({
                "day": i + 1,
                "high": 75 + i,
                "low": 65 + i,
                "conditions": ["sunny", "cloudy", "rainy"][i % 3],
            })
        
        return forecast


# Example 3: Streaming operations
@async_op(name="stream_events")
async def stream_events(count: int = 10) -> list[dict[str, Any]]:
    """Generate a stream of events."""
    events = []
    for i in range(count):
        await asyncio.sleep(0.1)  # Simulate event generation
        events.append({
            "event_id": i,
            "type": "measurement",
            "value": 50 + i * 2,
            "timestamp": f"2024-01-15T10:{30+i:02d}:00Z",
        })
    return events


async def main():
    """Main example demonstrating async Weave client usage."""
    
    # Create async client
    async with await create_async_client(
        entity="example-entity",
        project="async-demo",
        ensure_project_exists=True
    ) as client:
        
        print("=== Example 1: Basic Async Operations ===")
        
        # Fetch data
        data = await fetch_data("https://api.example.com/weather")
        print(f"Fetched data: {data}")
        
        # Process data
        processed = await process_data(data)
        print(f"Processed result: {processed}")
        
        # Save objects
        data_ref = await client.save(data, "weather_data")
        print(f"Saved data with ref: {data_ref}")
        
        # Retrieve objects
        retrieved_data = await client.get(data_ref)
        print(f"Retrieved data: {retrieved_data}")
        
        print("\n=== Example 2: Batch Processing ===")
        
        # Create batch of items
        batch_items = [
            await fetch_data(f"https://api.example.com/sensor/{i}")
            for i in range(5)
        ]
        
        # Analyze batch
        batch_result = await analyze_batch(batch_items)
        print(f"Batch analysis result: {batch_result}")
        
        print("\n=== Example 3: Service-based Operations ===")
        
        # Use weather service
        weather_service = AsyncWeatherService()
        
        # Get current weather for multiple cities concurrently
        cities = ["New York", "London", "Tokyo", "Sydney"]
        weather_tasks = [
            weather_service.get_current_weather(city)
            for city in cities
        ]
        weather_results = await asyncio.gather(*weather_tasks)
        
        for city, weather in zip(cities, weather_results):
            print(f"{city}: {weather['temperature']}°F, {weather['conditions']}")
        
        # Get forecast
        forecast = await weather_service.get_forecast("New York", days=3)
        print(f"\nForecast for New York: {forecast}")
        
        print("\n=== Example 4: Querying Calls ===")
        
        # Query recent calls
        calls = await client.calls(limit=10)
        print(f"\nFound {len(calls)} recent calls")
        
        for call in calls[:3]:
            print(f"- {call.op_name}: {call.status}")
        
        print("\n=== Example 5: Working with Tables ===")
        
        # Create a table
        table_data = [
            {"timestamp": "2024-01-15T10:00:00Z", "value": 100, "status": "ok"},
            {"timestamp": "2024-01-15T10:01:00Z", "value": 105, "status": "ok"},
            {"timestamp": "2024-01-15T10:02:00Z", "value": 98, "status": "warning"},
        ]
        
        table = await client.table("sensor_readings", rows=table_data)
        print(f"\nCreated table: {table.name}")
        
        print("\n=== Example 6: Feedback ===")
        
        # Add feedback to a call
        if calls:
            feedback_id = await client.feedback(
                call=calls[0],
                feedback_type="rating",
                payload={"score": 5, "comment": "Great performance!"}
            )
            print(f"\nAdded feedback: {feedback_id}")
            
            # Get feedback
            feedbacks = await client.get_feedback(call=calls[0])
            print(f"Retrieved {len(feedbacks)} feedback items")
        
        print("\n=== Example 7: Concurrent Operations ===")
        
        # Run multiple operations concurrently
        async def complex_workflow(item_id: int) -> dict[str, Any]:
            # Fetch, process, and analyze in a workflow
            data = await fetch_data(f"https://api.example.com/item/{item_id}")
            processed = await process_data(data)
            return {"item_id": item_id, "result": processed}
        
        # Execute workflows concurrently
        workflow_tasks = [complex_workflow(i) for i in range(3)]
        workflow_results = await asyncio.gather(*workflow_tasks)
        
        print("\nWorkflow results:")
        for result in workflow_results:
            print(f"- Item {result['item_id']}: {result['result']['comfort_level']}")
        
        print("\n=== Demo Complete ===")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())