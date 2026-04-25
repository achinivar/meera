"""Weather tool — fetch current conditions via wttr.in."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote_plus

from tools._cmd import run_argv
from tools.schema import ToolParam, ToolResult, ToolSpec, tool_result_err, tool_result_ok


def _weather_query(params: Mapping[str, Any]) -> ToolResult:
    _ = params["distro"]
    city = params.get("city", "").strip()
    if not city:
        return tool_result_err("city is required", "VALIDATION_ERROR")

    encoded = quote_plus(city)
    url_json = f"https://wttr.in/{encoded}?format=j1"

    r = run_argv(["curl", "-s", "--max-time", "15", url_json], timeout=15.0)
    if isinstance(r, ToolResult):
        pass
    elif r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            cond = data["current_condition"][0]
            weather = cond["weatherDescription"][0]["value"]
            temp = cond["temp_C"]
            feels = cond["FeelsLikeC"]
            humidity = cond["humidity"]
            wind = cond["windspeedMiles"]
            region = data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", city)
            country = data.get("nearest_area", [{}])[0].get("country", [{}])[0].get("value", "")
            return tool_result_ok(
                f"Weather for {region} ({country}): {weather}, {temp}°C (feels {feels}°C)",
                data={
                    "city": region,
                    "country": country,
                    "condition": weather,
                    "temp_c": temp,
                    "feels_like_c": feels,
                    "humidity": humidity,
                    "wind_speed_mph": wind,
                },
            )
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    url_txt = f"https://wttr.in/{encoded}?format=4"
    r2 = run_argv(["curl", "-s", "--max-time", "15", url_txt], timeout=15.0)
    if isinstance(r2, ToolResult):
        return tool_result_err(
            f"Could not fetch weather: {r2.message}. curl is required for this tool.",
            "COMMAND_FAILED",
        )
    if r2.returncode != 0:
        return tool_result_err(
            f"Failed to fetch weather: {r2.stderr or r2.stdout}",
            "COMMAND_FAILED",
        )
    return tool_result_ok(
        f"Weather for {city}: {r2.stdout.strip()}",
        data={"city": city, "compact": r2.stdout.strip()},
    )


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="weather_query",
        description=(
            "Get current weather for a city or IATA airport code using wttr.in."
            " Fetches detailed JSON, falls back to compact text format."
        ),
        parameters=[
            ToolParam(
                name="city",
                param_type="string",
                required=True,
                description="City name or 3-letter IATA airport code (e.g. London, JFK).",
            ),
        ],
        handler=_weather_query,
        read_only=True,
    ),
]
