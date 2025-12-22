import logging
import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import is_db_initialized
from .routes import router

# Configure logging for all app modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Endpoints to exclude from access logs (polling/SSE endpoints)
FILTERED_ENDPOINTS = [
    "/api/memories/events",
    "/api/settings/provider-status",
]


class EndpointFilter(logging.Filter):
    """Filter out noisy polling/SSE endpoints from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(endpoint in message for endpoint in FILTERED_ENDPOINTS)


# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger(__name__)
    
    # Ensure Playwright browsers are installed (for web research)
    await ensure_playwright_installed()
    
    # Register built-in tools
    from .tools import register_all_builtin_tools
    register_all_builtin_tools()
    
    # Load enabled plugins
    from .services.plugin_manager import get_plugin_manager
    plugin_manager = get_plugin_manager()
    try:
        # Auto-install bundled plugins (e.g., clippy-integration)
        plugin_manager.install_bundled_plugins()
        await plugin_manager.load_enabled_plugins()
        logger.info("Plugin system initialized")
    except Exception as e:
        logger.warning(f"Failed to load some plugins: {e}")
    
    # Start native messaging socket server for secure extension communication
    from .native_messaging import start_native_messaging_server, stop_native_messaging_server

    await start_native_messaging_server()
    yield
    
    # Unload all plugins on shutdown
    try:
        await plugin_manager.unload_all_plugins()
    except Exception as e:
        logger.warning(f"Error unloading plugins: {e}")
    
    await stop_native_messaging_server()


async def ensure_playwright_installed():
    """Ensure Playwright browsers are installed for web research."""
    import asyncio
    import subprocess
    import sys
    
    logger = logging.getLogger(__name__)
    
    try:
        # Check if Playwright is installed and browsers are available
        from playwright.async_api import async_playwright
        
        # Try to launch browser to verify it's installed
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
                logger.info("Playwright browsers already installed")
                return
            except Exception:
                # Browser not installed, need to install
                pass
        
        logger.info("Installing Playwright browsers (first-time setup)...")
        
        # Run playwright install chromium
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Playwright browsers installed successfully")
        else:
            logger.warning(f"Playwright install warning: {result.stderr}")
            
    except ImportError:
        logger.warning("Playwright not installed - web research will be unavailable")
    except Exception as e:
        logger.warning(f"Playwright setup failed: {e} - web research may be unavailable")


app = FastAPI(title="Think API", lifespan=lifespan)

# CORS restricted to Electron app origins only
# Browser extension uses native messaging (no HTTP), so it doesn't need CORS access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "file://",  # Electron production (loads from file://)
        "app://.",  # Electron custom protocol (if used)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths that don't require unlock
PUBLIC_PATHS = {
    "/health",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/unlock",
    "/api/settings/providers",  # Static provider config doesn't need DB
    "/api/settings/ollama-status",  # Ollama status check doesn't need DB
    "/api/settings/models",  # Model lists can be fetched without DB (for Morpheus/Ollama)
}


@app.middleware("http")
async def require_unlock_middleware(request: Request, call_next):
    """Block requests to protected endpoints if DB is not unlocked."""
    # Allow CORS preflight requests (OPTIONS) to pass through
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path not in PUBLIC_PATHS and not is_db_initialized():
        return JSONResponse(
            status_code=403,
            content={"detail": "Database not unlocked"}
        )
    return await call_next(request)


@app.middleware("http")
async def require_app_token_middleware(request: Request, call_next):
    """Validate X-App-Token header on all requests.

    This ensures only the Electron app can access the API.
    In dev mode (no token set), validation is bypassed.
    """
    # Allow CORS preflight requests (OPTIONS) to pass through
    if request.method == "OPTIONS":
        return await call_next(request)

    app_token = os.environ.get("THINK_APP_TOKEN", "")
    if not app_token:
        # Dev mode: no token configured, allow all requests
        return await call_next(request)

    request_token = request.headers.get("X-App-Token", "")
    if not secrets.compare_digest(request_token, app_token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: Invalid or missing app token"}
        )

    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(router)
