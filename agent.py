"""
Tool-Calling Agent
Agent decides which tools to use and what order.
Can't function outside of well-defined abilities.
"""

# --- IMPORTS ---
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agent_tracer import print_agent_trace
import datetime as dt
import csv
import httpx
import nest_asyncio

# --- SETUP ---
load_dotenv()
nest_asyncio.apply()
MODEL = "google:gemini-3-flash-preview"

with open("clothing_db.csv", "r") as file:
    reader = csv.DictReader(file)
    inventory = list(reader)


# --- Deps ---
@dataclass
class ClothingDeps:
    inventory: list[dict]
    user_location: str | None = None


# --- Output ---
class Recommendation(BaseModel):
    shirt: str
    pants_shorts: str
    jacket: str
    shoes: str


# --- Agent ---
weather_clothing_agent = Agent(
    MODEL,
    deps_type=ClothingDeps,
    output_type=Recommendation,
    system_prompt=(
        "You are a clothing outfit recommender agent. Use the available tools to look up "
        "the current location, the weather, and the inventory of clothing. Provide a recommended outfit. "
        "Always verify the outfit makes sense for the weather before sharing the outfit guidance."
    ),
)


# --- Tools ---
@weather_clothing_agent.tool
async def get_datetime(ctx: RunContext[ClothingDeps]) -> str:
    return f"Current time and date: {dt.datetime.now().isoformat()}"


@weather_clothing_agent.tool
async def get_location(ctx: RunContext[ClothingDeps]) -> str:
    if ctx.deps.user_location:
        return ctx.deps.user_location
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get("https://ipinfo.io/json")
        r.raise_for_status()
        data = r.json()
    return f"{data.get('city', '')}, {data.get('region', '')}".strip(", ")


@weather_clothing_agent.tool
async def get_weather(ctx: RunContext[ClothingDeps], location: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://wttr.in/{location}?format=%C+%t+wind+%w")
        r.raise_for_status()
    return f"Weather in {location}: {r.text.strip()}"


@weather_clothing_agent.tool
async def get_inventory(ctx: RunContext[ClothingDeps]) -> list[dict]:
    return ctx.deps.inventory


# --- Run ---
if __name__ == "__main__":
    import asyncio

    print(
        "If you want your location auto-detected (not permanent tracking), simply press Enter.\n"
        "Otherwise, enter a city, state, ZIP code, or full address.\n"
        "Type 'exit' (or press Ctrl+C) to quit."
    )

    try:
        while True:
            raw = input("\nLocation: ").strip()
            if raw.lower() == "exit":
                break
            deps = ClothingDeps(inventory=inventory, user_location=raw or None)

            result = asyncio.run(
                weather_clothing_agent.run(
                    "What should I wear today?",
                    deps=deps,
                )
            )

            print_agent_trace(result)
            print(f"\nShirt: {result.output.shirt}")
            print(f"Pants/Shorts: {result.output.pants_shorts}")
            print(f"Jacket: {result.output.jacket}")
            print(f"Shoes: {result.output.shoes}")
    except KeyboardInterrupt:
        pass

    print("\nGoodbye!")
