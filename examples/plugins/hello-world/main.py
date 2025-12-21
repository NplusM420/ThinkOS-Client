"""
Hello World Plugin for ThinkOS

This is an example plugin demonstrating how to create plugins for ThinkOS.
It shows how to:
- Define a plugin class
- Register tools
- Use the ThinkOS API
- Handle lifecycle events
"""

from typing import Any


class Plugin:
    """
    Main plugin class. ThinkOS will instantiate this with the plugin API.
    
    The plugin API (think_api) provides access to ThinkOS features based on
    the permissions declared in plugin.json.
    """
    
    def __init__(self, api: Any):
        """
        Initialize the plugin with the ThinkOS API.
        
        Args:
            api: The PluginAPI instance for interacting with ThinkOS
        """
        self.api = api
        self.api.log("info", "Hello World plugin initialized")
    
    async def on_load(self) -> None:
        """Called when the plugin is loaded/enabled."""
        self.api.log("info", "Hello World plugin loaded!")
    
    async def on_unload(self) -> None:
        """Called when the plugin is unloaded/disabled."""
        self.api.log("info", "Hello World plugin unloaded!")
    
    def register_tools(self) -> list[dict]:
        """
        Register tools that this plugin provides.
        
        Returns:
            List of tool definitions with handlers
        """
        return [
            {
                "name": "greet",
                "description": "Generate a friendly greeting message for a person",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the person to greet"
                        },
                        "style": {
                            "type": "string",
                            "description": "The greeting style",
                            "enum": ["formal", "casual", "enthusiastic"],
                            "default": "casual"
                        }
                    },
                    "required": ["name"]
                },
                "handler": self.greet_handler
            },
            {
                "name": "count_memories",
                "description": "Count the total number of memories stored in ThinkOS",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "handler": self.count_memories_handler
            },
            {
                "name": "search_memories_simple",
                "description": "Search memories with a simple query and return a summary",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                },
                "handler": self.search_memories_handler
            }
        ]
    
    async def greet_handler(self, params: dict) -> dict:
        """
        Handle the greet tool call.
        
        Args:
            params: Tool parameters (name, style)
            
        Returns:
            Result dictionary with the greeting
        """
        name = params.get("name", "friend")
        style = params.get("style", "casual")
        
        greetings = {
            "formal": f"Good day, {name}. It is a pleasure to make your acquaintance.",
            "casual": f"Hey {name}! How's it going?",
            "enthusiastic": f"WOW! {name}! SO GREAT to see you! 🎉"
        }
        
        greeting = greetings.get(style, greetings["casual"])
        
        return {
            "success": True,
            "result": {
                "greeting": greeting,
                "name": name,
                "style": style
            }
        }
    
    async def count_memories_handler(self, params: dict) -> dict:
        """
        Handle the count_memories tool call.
        
        Args:
            params: Tool parameters (none required)
            
        Returns:
            Result dictionary with memory count
        """
        try:
            # Use the plugin API to access memories
            memories = await self.api.get_memories(limit=1000)
            count = len(memories)
            
            return {
                "success": True,
                "result": {
                    "count": count,
                    "message": f"You have {count} memories stored in ThinkOS"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_memories_handler(self, params: dict) -> dict:
        """
        Handle the search_memories_simple tool call.
        
        Args:
            params: Tool parameters (query, limit)
            
        Returns:
            Result dictionary with search results summary
        """
        query = params.get("query", "")
        limit = params.get("limit", 5)
        
        if not query:
            return {
                "success": False,
                "error": "Query is required"
            }
        
        try:
            # Use the plugin API to search memories
            results = await self.api.search_memories(query, limit=int(limit))
            
            # Create a summary of results
            summaries = []
            for memory in results:
                title = memory.get("title", "Untitled")
                content = memory.get("content", "")[:100]
                summaries.append({
                    "title": title,
                    "preview": content + "..." if len(memory.get("content", "")) > 100 else content
                })
            
            return {
                "success": True,
                "result": {
                    "query": query,
                    "count": len(results),
                    "memories": summaries
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
