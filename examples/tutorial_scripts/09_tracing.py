import random

import requests
from openai import OpenAI

import weave

PROMPT = """Emulate the Pokedex from early Pokémon episodes. State the name of the Pokemon and then describe it.
        Your tone is informative yet sassy, blending factual details with a touch of dry humor. Be concise, no more than 3 sentences. """
POKEMON = [
    "pikachu",
    "charmander",
    "squirtle",
    "bulbasaur",
    "jigglypuff",
    "meowth",
    "eevee",
]


@weave.op()
def get_pokemon_data(pokemon_name):
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        name = data["name"]
        types = [t["type"]["name"] for t in data["types"]]
        species_url = data["species"]["url"]
        species_response = requests.get(species_url)
        evolved_from = "Unknown"
        if species_response.status_code == 200:
            species_data = species_response.json()
            if species_data["evolves_from_species"]:
                evolved_from = species_data["evolves_from_species"]["name"]
        return {"name": name, "types": types, "evolved_from": evolved_from}
    else:
        return None


@weave.op()
def pokedex(name: str, prompt: str) -> str:
    client = OpenAI()
    data = get_pokemon_data(name)
    if not data:
        return "Error: Unable to fetch data"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(data)},
        ],
        temperature=0.7,
        max_tokens=100,
        top_p=1,
    )
    return response.choices[0].message.content


weave.init("intro-example")
# Get data for a specific Pokémon
pokemon_data = pokedex(random.choice(POKEMON), PROMPT)

import json

from openai import OpenAI

import weave


@weave.op()
def extract_fruit(sentence: str) -> dict:
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with unstructured data, and your task is to parse it one JSON dictionary with fruit, color and flavor as keys.",
            },
            {"role": "user", "content": sentence},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    extracted = response.choices[0].message.content
    return json.loads(extracted)


weave.init("intro-example")
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."

with weave.attributes({"user_id": "lukas", "env": "production"}):
    extract_fruit(sentence)
