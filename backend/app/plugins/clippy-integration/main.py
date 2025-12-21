"""
Clippy Integration Plugin for ThinkOS

Integrates with the Clipper platform to create video clips using the Clippy AI agent.
Allows ThinkOS agents to send video URLs and prompts to Clipper and receive
generated clips with captions and aspect ratios.

The clips are automatically saved to the ThinkOS clips library for future reference.

API Spec:
- Authentication: Bearer token or X-API-Key header (keys start with 'clipper_')
- Base URL: {clipper_url}/api/v1/clippy
- Endpoints: /health, /generate, /jobs/:jobId
"""

import json
import asyncio
from typing import Any
from datetime import datetime


class Plugin:
    """
    Clippy integration plugin that connects ThinkOS with the Clipper platform.
    
    Configuration (set via plugin settings):
    - clipper_api_url: Base URL of the Clipper API (e.g., http://localhost:5000)
    - clipper_api_key: API key for authenticating with Clipper (starts with 'clipper_')
    - auto_save_clips: Automatically save returned clips to library
    - poll_interval: Seconds between job status polls (default: 4)
    """
    
    DEFAULT_CLIPPER_URL = "https://clippy.up.railway.app"
    DEFAULT_POLL_INTERVAL = 4  # seconds
    
    def __init__(self, api: Any):
        self.api = api
        self.api.log("info", "Clippy Integration plugin initialized")
        # Cache for health check data
        self._health_cache: dict | None = None
        self._health_cache_time: float = 0
    
    async def on_load(self) -> None:
        """Load plugin settings and perform health check."""
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        api_key = self.api.get_config("clipper_api_key", "")
        
        self.api.log("info", f"Clippy Integration loaded - API URL: {api_url}")
        
        if not api_key:
            self.api.log("warning", "Clipper API key not configured. Go to Settings > Plugins > Clippy to set it up.")
            return
        
        # Perform health check on load
        try:
            health = await self._check_health()
            if health.get("success"):
                account = health.get("account", {})
                self.api.log("info", f"Connected to Clipper - Balance: {account.get('creditBalance', 0)} credits")
            else:
                self.api.log("warning", f"Clipper health check failed: {health.get('error', 'Unknown error')}")
        except Exception as e:
            self.api.log("warning", f"Could not connect to Clipper: {e}")
    
    async def on_unload(self) -> None:
        """Cleanup on unload."""
        self.api.log("info", "Clippy Integration plugin unloaded")
    
    def register_tools(self) -> list[dict]:
        """Register Clippy tools for ThinkOS agents."""
        return [
            {
                "name": "clippy_create_clips",
                "description": "Send a video URL to Clippy AI agent to create clips based on a prompt. Clippy will analyze the video, find the best moments, and return clips with captions and aspect ratio recommendations. Use this when the user wants to create short clips from a video.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_url": {
                            "type": "string",
                            "description": "URL of the video to create clips from (YouTube, direct video URL, etc.)"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Instructions for what kind of clips to create (e.g., 'Find the funniest moments', 'Create educational highlights', 'Extract key product demos')"
                        },
                        "target_platform": {
                            "type": "string",
                            "description": "Target social media platform for the clips",
                            "enum": ["tiktok", "youtube_shorts", "instagram_reels", "linkedin", "twitter", "general"],
                            "default": "general"
                        },
                        "max_clips": {
                            "type": "number",
                            "description": "Maximum number of clips to generate (1-10)",
                            "default": 5
                        },
                        "include_captions": {
                            "type": "boolean",
                            "description": "Whether to include auto-generated captions",
                            "default": True
                        }
                    },
                    "required": ["video_url", "prompt"]
                },
                "handler": self.create_clips_handler
            },
            {
                "name": "clippy_check_status",
                "description": "Check the status of a clip generation job that was previously submitted to Clippy",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The job ID returned from clippy_create_clips"
                        }
                    },
                    "required": ["job_id"]
                },
                "handler": self.check_status_handler
            },
            {
                "name": "clippy_get_clip",
                "description": "Get details and download URL for a specific clip that was generated by Clippy",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clip_id": {
                            "type": "string",
                            "description": "The clip ID to retrieve"
                        }
                    },
                    "required": ["clip_id"]
                },
                "handler": self.get_clip_handler
            },
            {
                "name": "clippy_status",
                "description": "Check the current Clippy integration status including connection health, credit balance, and available features. Use this to verify the connection before generating clips.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "refresh": {
                            "type": "boolean",
                            "description": "Force refresh the health check (bypass cache)",
                            "default": False
                        }
                    },
                    "required": []
                },
                "handler": self.status_handler
            },
            {
                "name": "clippy_wait_for_job",
                "description": "Wait for a clip generation job to complete by polling its status. Returns the completed clips when done. Use this after clippy_create_clips returns a job_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "The job ID returned from clippy_create_clips"
                        },
                        "max_wait_seconds": {
                            "type": "number",
                            "description": "Maximum seconds to wait for completion (default: 300 = 5 minutes)",
                            "default": 300
                        }
                    },
                    "required": ["job_id"]
                },
                "handler": self.wait_for_job_handler
            }
        ]
    
    async def create_clips_handler(self, params: dict) -> dict:
        """
        Send a video to Clippy for clip generation.
        
        This calls the Clipper API's /api/v1/clippy/generate endpoint.
        """
        video_url = params.get("video_url", "")
        prompt = params.get("prompt", "")
        target_platform = params.get("target_platform", "general")
        max_clips = min(max(int(params.get("max_clips", 5)), 1), 10)
        include_captions = params.get("include_captions", True)
        
        if not video_url:
            return {"success": False, "error": "video_url is required"}
        
        if not prompt:
            return {"success": False, "error": "prompt is required"}
        
        api_key = self.api.get_config("clipper_api_key", "")
        if not api_key:
            return {
                "success": False,
                "error": "Clipper API key not configured. Go to Settings > Plugins > Clippy to set it up."
            }
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        
        try:
            # Call Clipper's Clippy agent endpoint
            response = await self.api.http_request(
                method="POST",
                url=f"{api_url}/api/v1/clippy/generate",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                body=json.dumps({
                    "videoUrl": video_url,
                    "prompt": prompt,
                    "targetPlatform": target_platform,
                    "maxClips": max_clips,
                    "includeCaptions": include_captions,
                    "callbackUrl": None  # Could add webhook support later
                }),
                timeout=120.0  # Video processing can take time
            )
            
            status_code = response["status_code"]
            
            if status_code == 401:
                return {
                    "success": False,
                    "error": "Invalid or expired Clipper API key. Please re-enter your API key in Settings > Plugins > Clippy."
                }
            
            if status_code == 402:
                # Insufficient credits
                try:
                    error_data = json.loads(response["body"])
                    return {
                        "success": False,
                        "error": "insufficient_credits",
                        "message": error_data.get("message", "You need more Clipper credits to generate clips."),
                        "required": error_data.get("required", 100),
                        "balance": error_data.get("balance", 0),
                        "purchase_url": error_data.get("purchaseUrl", "/settings?tab=credits")
                    }
                except:
                    return {
                        "success": False,
                        "error": "insufficient_credits",
                        "message": "You need more Clipper credits to generate clips."
                    }
            
            if status_code == 403:
                return {
                    "success": False,
                    "error": "Your API key is missing the 'clippy_agent' permission. Please regenerate your key with the correct permissions."
                }
            
            if status_code == 404:
                return {
                    "success": False,
                    "error": "Clippy endpoint not found. Make sure Clipper has the /api/v1/clippy/generate endpoint enabled."
                }
            
            if status_code == 429:
                # Parse retry-after from response
                retry_after = 30  # default
                try:
                    error_data = json.loads(response["body"])
                    retry_after = error_data.get("retryAfter", 30)
                except:
                    pass
                return {
                    "success": False,
                    "error": "rate_limited",
                    "message": f"Rate limited. Please wait {retry_after} seconds and try again.",
                    "retry_after": retry_after
                }
            
            if status_code != 200 and status_code != 202:
                return {
                    "success": False,
                    "error": f"Clipper API error: {status_code} - {response.get('body', '')}"
                }
            
            result = json.loads(response["body"])
            
            # If clips are returned immediately (sync mode)
            if result.get("clips"):
                clips = result["clips"]
                
                # Auto-save clips as memories if enabled
                if self.api.get_config("auto_save_clips", True):
                    await self._save_clips_as_memories(clips, video_url, prompt)
                
                return {
                    "success": True,
                    "result": {
                        "status": "completed",
                        "video_url": video_url,
                        "clips_count": len(clips),
                        "clips": clips
                    }
                }
            
            # If async mode, return job ID
            return {
                "success": True,
                "result": {
                    "status": "processing",
                    "job_id": result.get("jobId"),
                    "message": result.get("message", "Clip generation started"),
                    "estimated_time": result.get("estimatedTime", "1-5 minutes")
                }
            }
            
        except Exception as e:
            self.api.log("error", f"Clippy API error: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_status_handler(self, params: dict) -> dict:
        """Check the status of a clip generation job."""
        job_id = params.get("job_id", "")
        
        if not job_id:
            return {"success": False, "error": "job_id is required"}
        
        api_key = self.api.get_config("clipper_api_key", "")
        if not api_key:
            return {"success": False, "error": "Clipper API key not configured"}
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        
        try:
            response = await self.api.http_request(
                method="GET",
                url=f"{api_url}/api/v1/clippy/jobs/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0
            )
            
            if response["status_code"] != 200:
                return {"success": False, "error": f"Failed to get job status: {response['status_code']}"}
            
            result = json.loads(response["body"])
            
            # If job is complete and has clips, auto-save them
            if result.get("status") == "completed" and result.get("clips"):
                if self.api.get_config("auto_save_clips", True):
                    await self._save_clips_as_memories(
                        result["clips"],
                        result.get("videoUrl", ""),
                        result.get("prompt", "")
                    )
            
            return {
                "success": True,
                "result": {
                    "job_id": job_id,
                    "status": result.get("status"),
                    "progress": result.get("progress", 0),
                    "clips_count": len(result.get("clips", [])),
                    "clips": result.get("clips", []),
                    "error": result.get("error")
                }
            }
            
        except Exception as e:
            self.api.log("error", f"Status check error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_clip_handler(self, params: dict) -> dict:
        """Get details for a specific clip."""
        clip_id = params.get("clip_id", "")
        
        if not clip_id:
            return {"success": False, "error": "clip_id is required"}
        
        api_key = self.api.get_config("clipper_api_key", "")
        if not api_key:
            return {"success": False, "error": "Clipper API key not configured"}
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        
        try:
            response = await self.api.http_request(
                method="GET",
                url=f"{api_url}/api/v1/clippy/clips/{clip_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0
            )
            
            if response["status_code"] != 200:
                return {"success": False, "error": f"Failed to get clip: {response['status_code']}"}
            
            result = json.loads(response["body"])
            
            return {
                "success": True,
                "result": {
                    "clip_id": clip_id,
                    "title": result.get("title"),
                    "description": result.get("description"),
                    "duration": result.get("duration"),
                    "start_time": result.get("startTime"),
                    "end_time": result.get("endTime"),
                    "download_url": result.get("downloadUrl"),
                    "thumbnail_url": result.get("thumbnailUrl"),
                    "captions": result.get("captions"),
                    "aspect_ratio": result.get("aspectRatio"),
                    "platform_recommendation": result.get("platformRecommendation")
                }
            }
            
        except Exception as e:
            self.api.log("error", f"Get clip error: {e}")
            return {"success": False, "error": str(e)}
    
    async def status_handler(self, params: dict) -> dict:
        """
        Check Clippy integration status with full health check.
        
        Returns connection status, credit balance, and available features.
        """
        refresh = params.get("refresh", False)
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        api_key = self.api.get_config("clipper_api_key", "")
        auto_save = self.api.get_config("auto_save_clips", True)
        
        if not api_key:
            return {
                "success": False,
                "error": "Clipper API key not configured. Go to Settings > Plugins > Clippy to set it up.",
                "result": {
                    "connected": False,
                    "api_url": api_url,
                    "api_key_configured": False
                }
            }
        
        # Perform health check
        health = await self._check_health(force_refresh=refresh)
        
        if not health.get("success"):
            return {
                "success": False,
                "error": health.get("error", "Failed to connect to Clipper"),
                "result": {
                    "connected": False,
                    "api_url": api_url,
                    "api_key_configured": True
                }
            }
        
        account = health.get("account", {})
        features = health.get("features", {})
        api_key_info = health.get("apiKey", {})
        
        return {
            "success": True,
            "result": {
                "connected": True,
                "api_url": api_url,
                "api_key_configured": True,
                "api_key_name": api_key_info.get("name", "Unknown"),
                "auto_save_clips": auto_save,
                "account": {
                    "credit_balance": account.get("creditBalance", 0),
                    "minimum_required": account.get("minimumRequired", 100),
                    "can_generate_clips": account.get("canGenerateClips", False)
                },
                "features": {
                    "platforms": features.get("platforms", []),
                    "max_clips": features.get("maxClips", 10),
                    "include_captions": features.get("includeCaptions", True),
                    "webhooks": features.get("webhooks", False)
                },
                "service_version": health.get("version", "unknown")
            }
        }
    
    async def wait_for_job_handler(self, params: dict) -> dict:
        """
        Wait for a clip generation job to complete by polling.
        
        Polls the job status every few seconds until completion or timeout.
        """
        job_id = params.get("job_id", "")
        max_wait = min(params.get("max_wait_seconds", 300), 600)  # Cap at 10 minutes
        
        if not job_id:
            return {"success": False, "error": "job_id is required"}
        
        api_key = self.api.get_config("clipper_api_key", "")
        if not api_key:
            return {"success": False, "error": "Clipper API key not configured"}
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        poll_interval = self.api.get_config("poll_interval", self.DEFAULT_POLL_INTERVAL)
        
        start_time = asyncio.get_event_loop().time()
        last_progress = -1
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait:
                return {
                    "success": False,
                    "error": f"Timeout waiting for job {job_id} after {max_wait} seconds",
                    "result": {
                        "job_id": job_id,
                        "status": "timeout",
                        "elapsed_seconds": int(elapsed)
                    }
                }
            
            try:
                response = await self.api.http_request(
                    method="GET",
                    url=f"{api_url}/api/v1/clippy/jobs/{job_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30.0
                )
                
                if response["status_code"] == 404:
                    return {"success": False, "error": f"Job {job_id} not found"}
                
                if response["status_code"] != 200:
                    return {"success": False, "error": f"Failed to get job status: {response['status_code']}"}
                
                result = json.loads(response["body"])
                status = result.get("status", "unknown")
                progress = result.get("progress", 0)
                
                # Log progress updates
                if progress != last_progress:
                    self.api.log("info", f"Job {job_id}: {status} ({progress}%)")
                    last_progress = progress
                
                if status == "completed":
                    clips = result.get("clips", [])
                    
                    # Auto-save clips if enabled
                    if clips and self.api.get_config("auto_save_clips", True):
                        await self._save_clips_as_memories(
                            clips,
                            result.get("videoUrl", ""),
                            result.get("prompt", ""),
                            job_id
                        )
                    
                    return {
                        "success": True,
                        "result": {
                            "job_id": job_id,
                            "status": "completed",
                            "progress": 100,
                            "elapsed_seconds": int(elapsed),
                            "clips_count": len(clips),
                            "clips": clips
                        }
                    }
                
                if status == "failed":
                    return {
                        "success": False,
                        "error": result.get("error", "Job failed"),
                        "result": {
                            "job_id": job_id,
                            "status": "failed",
                            "elapsed_seconds": int(elapsed)
                        }
                    }
                
                # Still processing, wait and poll again
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                self.api.log("error", f"Error polling job {job_id}: {e}")
                return {"success": False, "error": str(e)}
    
    async def _check_health(self, force_refresh: bool = False) -> dict:
        """
        Check Clipper API health and get account info.
        
        Caches the result for 60 seconds to avoid excessive API calls.
        """
        import time
        
        # Return cached result if fresh (within 60 seconds)
        if not force_refresh and self._health_cache:
            if time.time() - self._health_cache_time < 60:
                return self._health_cache
        
        api_key = self.api.get_config("clipper_api_key", "")
        if not api_key:
            return {"success": False, "error": "API key not configured"}
        
        api_url = self.api.get_config("clipper_api_url", self.DEFAULT_CLIPPER_URL)
        
        try:
            response = await self.api.http_request(
                method="GET",
                url=f"{api_url}/api/v1/clippy/health",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            
            if response["status_code"] == 401:
                return {"success": False, "error": "Invalid or expired API key"}
            
            if response["status_code"] == 403:
                return {"success": False, "error": "API key missing required permissions"}
            
            if response["status_code"] != 200:
                return {"success": False, "error": f"Health check failed: {response['status_code']}"}
            
            result = json.loads(response["body"])
            
            # Cache the successful result
            self._health_cache = result
            self._health_cache_time = time.time()
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _save_clips_as_memories(
        self,
        clips: list[dict],
        video_url: str,
        prompt: str,
        job_id: str | None = None
    ) -> None:
        """Save generated clips to the clips library in ThinkOS."""
        for clip in clips:
            try:
                title = clip.get("title", "Untitled Clip")
                
                # Build tags list
                tags = ["clippy"]
                if clip.get("platformRecommendation"):
                    tags.append(clip["platformRecommendation"])
                
                # Save to dedicated clips table
                await self.api.save_video_clip(
                    title=title,
                    source_url=video_url,
                    description=clip.get("description"),
                    start_time=clip.get("startTime"),
                    end_time=clip.get("endTime"),
                    duration=clip.get("duration"),
                    thumbnail_url=clip.get("thumbnailUrl"),
                    download_url=clip.get("downloadUrl"),
                    preview_url=clip.get("previewUrl"),
                    aspect_ratio=clip.get("aspectRatio"),
                    platform_recommendation=clip.get("platformRecommendation"),
                    captions=clip.get("captions"),
                    prompt=prompt,
                    clippy_job_id=job_id,
                    clippy_clip_id=clip.get("id"),
                    tags=tags,
                )
                
                self.api.log("info", f"Saved clip to library: {title}")
                
            except Exception as e:
                self.api.log("warning", f"Failed to save clip: {e}")
