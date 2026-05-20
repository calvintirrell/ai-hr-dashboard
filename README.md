# gemini_ai_agent_tool_calling

A Gemini-powered AI agent built with [pydantic-ai](https://ai.pydantic.dev/) that recommends a daily outfit by autonomously calling tools to check the current time, your location, the local weather, and your clothing inventory.

## What it does

You run `agent.py`, optionally type a location (or press Enter to auto-detect via IP), and the agent decides on its own which tools to call and in what order to answer **"What should I wear today?"**. It returns a structured recommendation:

```
Shirt: ...
Pants/Shorts: ...
Jacket: ...
Shoes: ...
```

An agent trace is printed first so you can see each tool call, its arguments, and what it returned.

### Tools the agent can call

| Tool | Purpose |
| --- | --- |
| `get_datetime` | Current local date/time |
| `get_location` | User-supplied location, or auto-detect via [ipinfo.io](https://ipinfo.io) |
| `get_weather` | Conditions, temperature, and wind from [wttr.in](https://wttr.in) |
| `get_inventory` | Loads available clothing from `clothing_db.csv` |

The agent's output is validated against a Pydantic `Recommendation` schema (shirt / pants_shorts / jacket / shoes).

## Project layout

```
agent.py            # Agent definition, tools, and CLI loop
agent_tracer.py     # Pretty-prints the agent's tool calls and final response
clothing_db.csv     # Your clothing inventory (edit this with what you own)
.env                # GEMINI_API_KEY (not committed)
```

## Setup

### 1. Clone

```bash
git clone https://github.com/calvintirrell/gemini_ai_agent_tool_calling.git
cd gemini_ai_agent_tool_calling
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install pydantic pydantic-ai python-dotenv httpx nest-asyncio
```

### 4. Add your Gemini API key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 5. (Optional) Customize your wardrobe

Edit `clothing_db.csv` — the header row is `Shirts,Pants_Shorts,Jackets,Shoes` and each row is one option per column.

## Run

```bash
python agent.py
```

You'll be prompted for a location. Press Enter to auto-detect, type a city/ZIP/address, or type `exit` to quit. The agent will run, print its trace, and print the outfit.

## Model

Default model is `google:gemini-3-flash-preview` (set in `agent.py`). Change the `MODEL` constant to swap in another Gemini variant.
