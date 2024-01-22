---
sidebar_position: 2
hide_table_of_contents: true
---

# Tracing

Tracing is a powerful feature in Weave that allows you to track the inputs and outputs of functions seamlessly. Follow these steps to get started:

To track specific functions, decorate them with @weave.op(). This decorator tells Weave to monitor the inputs, outputs, and any code changes for the function.

```python
# highlight-next-line
import weave
from openai import OpenAI
import requests, random
PROMPT="""Emulate the Pokedex from early Pokémon episodes. State the name of the Pokemon and then describe it.
        Your tone is informative yet sassy, blending factual details with a touch of dry humor. Be concise, no more than 3 sentences. """
POKEMON = ['pikachu', 'charmander', 'squirtle', 'bulbasaur', 'jigglypuff', 'meowth', 'eevee']

# highlight-next-line
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

# highlight-next-line
@weave.op()
def pokedex(name: str, prompt: str) -> str:
    client = OpenAI()
    data = get_pokemon_data(name)
    if not data: return "Error: Unable to fetch data"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system","content": prompt},
            {"role": "user", "content": str(data)}
        ],
        temperature=0.7,
        max_tokens=100,
        top_p=1
    )
    return response.choices[0].message.content

# highlight-next-line
weave.init('pokedex')
# Get data for a specific Pokémon
pokemon_data = pokedex(random.choice(POKEMON), PROMPT)
```
