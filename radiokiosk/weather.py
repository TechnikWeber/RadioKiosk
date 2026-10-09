"""Weather forecast from Open-Meteo (free, no account needed)."""

import time

import aiohttp

URL = "https://api.open-meteo.com/v1/forecast"
KEEP = 15 * 60   # seconds a forecast stays fresh


class Weather:
    def __init__(self):
        self.cached = None
        self.cached_for = None
        self.fetched = 0

    async def get(self, location):
        if location is None:
            raise RuntimeError("no location set")
        if self.cached and self.cached_for == location and time.time() - self.fetched < KEEP:
            return self.cached
        params = {
            "latitude": location[0], "longitude": location[1], "timezone": "auto", "forecast_days": 4,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as http:
                async with http.get(URL, params=params) as r:
                    r.raise_for_status()
                    data = await r.json()
        except (aiohttp.ClientError, TimeoutError) as e:
            raise RuntimeError(f"weather service unreachable: {e}")
        daily = data["daily"]
        self.cached = {
            "now": {"temperature": data["current"]["temperature_2m"], "code": data["current"]["weather_code"],
                    "wind": data["current"]["wind_speed_10m"]},
            "days": [{"date": daily["time"][i], "code": daily["weather_code"][i],
                      "max": daily["temperature_2m_max"][i], "min": daily["temperature_2m_min"][i],
                      "rain": daily["precipitation_probability_max"][i]} for i in range(len(daily["time"]))],
        }
        self.cached_for, self.fetched = location, time.time()
        return self.cached
