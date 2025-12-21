"""
Weather Tool Plugin for ThinkOS

Demonstrates how to create a plugin that makes external API calls.
Uses the Open-Meteo API (free, no API key required) for weather data.
"""

from typing import Any


class Plugin:
    """Weather tool plugin providing weather information to agents."""
    
    # Open-Meteo API (free, no key required)
    GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_API = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, api: Any):
        self.api = api
        self.api.log("info", "Weather Tool plugin initialized")
    
    async def on_load(self) -> None:
        self.api.log("info", "Weather Tool plugin loaded")
    
    async def on_unload(self) -> None:
        self.api.log("info", "Weather Tool plugin unloaded")
    
    def register_tools(self) -> list[dict]:
        return [
            {
                "name": "get_weather",
                "description": "Get current weather and forecast for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name or location (e.g., 'New York', 'London, UK')"
                        },
                        "units": {
                            "type": "string",
                            "description": "Temperature units",
                            "enum": ["celsius", "fahrenheit"],
                            "default": "fahrenheit"
                        }
                    },
                    "required": ["location"]
                },
                "handler": self.get_weather_handler
            },
            {
                "name": "get_forecast",
                "description": "Get multi-day weather forecast for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name or location"
                        },
                        "days": {
                            "type": "number",
                            "description": "Number of forecast days (1-7)",
                            "default": 3
                        },
                        "units": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "default": "fahrenheit"
                        }
                    },
                    "required": ["location"]
                },
                "handler": self.get_forecast_handler
            }
        ]
    
    async def _geocode_location(self, location: str) -> dict | None:
        """Convert location name to coordinates."""
        try:
            url = f"{self.GEOCODING_API}?name={location}&count=1&language=en&format=json"
            response = await self.api.http_request("GET", url)
            
            if response["status_code"] != 200:
                return None
            
            import json
            data = json.loads(response["body"])
            
            if not data.get("results"):
                return None
            
            result = data["results"][0]
            return {
                "name": result.get("name"),
                "country": result.get("country"),
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                "timezone": result.get("timezone")
            }
        except Exception as e:
            self.api.log("error", f"Geocoding failed: {e}")
            return None
    
    async def get_weather_handler(self, params: dict) -> dict:
        """Get current weather for a location."""
        location = params.get("location", "")
        units = params.get("units", "fahrenheit")
        
        if not location:
            return {"success": False, "error": "Location is required"}
        
        # Geocode the location
        geo = await self._geocode_location(location)
        if not geo:
            return {"success": False, "error": f"Could not find location: {location}"}
        
        # Get weather data
        try:
            temp_unit = "fahrenheit" if units == "fahrenheit" else "celsius"
            url = (
                f"{self.WEATHER_API}?"
                f"latitude={geo['latitude']}&longitude={geo['longitude']}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&temperature_unit={temp_unit}"
                f"&wind_speed_unit=mph"
                f"&timezone={geo.get('timezone', 'auto')}"
            )
            
            response = await self.api.http_request("GET", url)
            
            if response["status_code"] != 200:
                return {"success": False, "error": "Failed to fetch weather data"}
            
            import json
            data = json.loads(response["body"])
            current = data.get("current", {})
            
            weather_desc = self._get_weather_description(current.get("weather_code", 0))
            temp_symbol = "°F" if units == "fahrenheit" else "°C"
            
            return {
                "success": True,
                "result": {
                    "location": f"{geo['name']}, {geo['country']}",
                    "temperature": f"{current.get('temperature_2m', 'N/A')}{temp_symbol}",
                    "humidity": f"{current.get('relative_humidity_2m', 'N/A')}%",
                    "wind_speed": f"{current.get('wind_speed_10m', 'N/A')} mph",
                    "conditions": weather_desc,
                    "coordinates": {
                        "lat": geo["latitude"],
                        "lon": geo["longitude"]
                    }
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_forecast_handler(self, params: dict) -> dict:
        """Get multi-day forecast for a location."""
        location = params.get("location", "")
        days = min(max(int(params.get("days", 3)), 1), 7)
        units = params.get("units", "fahrenheit")
        
        if not location:
            return {"success": False, "error": "Location is required"}
        
        geo = await self._geocode_location(location)
        if not geo:
            return {"success": False, "error": f"Could not find location: {location}"}
        
        try:
            temp_unit = "fahrenheit" if units == "fahrenheit" else "celsius"
            url = (
                f"{self.WEATHER_API}?"
                f"latitude={geo['latitude']}&longitude={geo['longitude']}"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                f"&temperature_unit={temp_unit}"
                f"&timezone={geo.get('timezone', 'auto')}"
                f"&forecast_days={days}"
            )
            
            response = await self.api.http_request("GET", url)
            
            if response["status_code"] != 200:
                return {"success": False, "error": "Failed to fetch forecast data"}
            
            import json
            data = json.loads(response["body"])
            daily = data.get("daily", {})
            
            temp_symbol = "°F" if units == "fahrenheit" else "°C"
            forecast = []
            
            dates = daily.get("time", [])
            highs = daily.get("temperature_2m_max", [])
            lows = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])
            precip = daily.get("precipitation_probability_max", [])
            
            for i in range(min(days, len(dates))):
                forecast.append({
                    "date": dates[i] if i < len(dates) else "N/A",
                    "high": f"{highs[i]}{temp_symbol}" if i < len(highs) else "N/A",
                    "low": f"{lows[i]}{temp_symbol}" if i < len(lows) else "N/A",
                    "conditions": self._get_weather_description(codes[i] if i < len(codes) else 0),
                    "precipitation_chance": f"{precip[i]}%" if i < len(precip) else "N/A"
                })
            
            return {
                "success": True,
                "result": {
                    "location": f"{geo['name']}, {geo['country']}",
                    "days": days,
                    "forecast": forecast
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_weather_description(self, code: int) -> str:
        """Convert WMO weather code to description."""
        descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return descriptions.get(code, "Unknown")
