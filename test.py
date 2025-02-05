import weave
from google import genai


weave.init(project_name="gemini-test")
client = genai.Client(api_key="AIzaSyBiYf-E95RSI7bUeZL-3JyPd16N2Fd1YF8")

get_destination = genai.types.FunctionDeclaration(
    name="get_destination",
    description="Get the destination that the user wants to go to",
    parameters={
        "type": "OBJECT",
        "properties": {
            "destination": {
                "type": "STRING",
                "description": "Destination that the user wants to go to",
            },
        },
    },
)

destination_tool = genai.types.Tool(
    function_declarations=[get_destination],
)

response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents="I'd like to travel to Paris.",
    config=genai.types.GenerateContentConfig(
        tools=[destination_tool],
        temperature=0,
        ),
)

print(response.candidates[0].content.parts[0].function_call)