"""
Stable Diffusion API Client

This module provides an async client for interacting with Stable Diffusion web UI API.
It supports text-to-image generation and model/sampler management.

Example:
    ```python
    async def generate_image():
        client = StableDiffusion("http://localhost:7860")
        
        config = SDConfig(
            prompt="a cute cat, high quality, detailed",
            negative_prompt="low quality, blurry"
        )
        
        try:
            images = await client.text2img(config)
            with open("generated.png", "wb") as f:
                f.write(images[0])
        finally:
            await client.close()
    ```
"""

import aiohttp
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import base64
from contextlib import asynccontextmanager
import asyncio
import random
from utils.logger import Logger

@dataclass
class SDConfig:
    """Configuration parameters for Stable Diffusion image generation.
    
    Attributes:
        prompt (str): The main prompt describing desired image
        negative_prompt (str, optional): Things to avoid in generation
        steps (int, optional): Number of denoising steps (default: 24)
        cfg_scale (float, optional): Classifier free guidance scale (default: 4.5)
        width (int, optional): Image width in pixels (default: 1024)
        height (int, optional): Image height in pixels (default: 1024)
        seed (int, optional): Random seed (-1 for random) (default: -1)
        batch_size (int, optional): Number of images per batch (default: 1)
        n_iter (int, optional): Number of batches to generate (default: 1)
        sampler_name (str, optional): Name of sampler to use (default: "Euler a")
    """
    
    prompt: str
    negative_prompt: str = ""
    steps: int = 24
    cfg_scale: float = 4.5
    width: int = 1024
    height: int = 1024
    seed: int = -1
    batch_size: int = 1
    n_iter: int = 1
    sampler_name: str = "Euler a"

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for API payload."""
        return asdict(self)

@dataclass
class ServerInfo:
    """Information about a Stable Diffusion server.
    
    Attributes:
        url (str): Base URL of the server
        is_alive (bool): Current status of the server
        last_checked (float): Timestamp of last health check
    """
    url: str
    is_alive: bool = False
    last_checked: float = 0

class StableDiffusion:
    """Async client for Stable Diffusion API.
    
    This client provides methods to interact with a Stable Diffusion web UI API endpoint
    for text-to-image generation and model management.
    
    Attributes:
        base_urls (Union[str, List[str]]): Base URLs of the Stable Diffusion API
        timeout (aiohttp.ClientTimeout): Request timeout configuration
        session (Optional[aiohttp.ClientSession]): Async HTTP session
        
    Args:
        base_urls (Union[str, List[str]]): Base URLs of the Stable Diffusion API
        timeout (int, optional): Request timeout in seconds (default: 300)
        health_check_interval (int, optional): Health check interval in seconds (default: 60)
    """
    
    def __init__(self, base_urls: Union[str, List[str]], timeout: int = 300, health_check_interval: int = 60):
        if isinstance(base_urls, str):
            base_urls = [base_urls]
            
        self.servers = [ServerInfo(url.rstrip('/')) for url in base_urls]
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.health_check_interval = health_check_interval
        self._health_check_task: Optional[asyncio.Task] = None
        self.logger = Logger(name="stable_diffusion")


    @asynccontextmanager
    async def _session(self):
        """Context manager for handling the aiohttp session.
        
        Yields:
            aiohttp.ClientSession: The active session
        """
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        try:
            yield self.session
        finally:
            if self.session and self.session.closed:
                self.session = None

    async def _health_check(self, server: ServerInfo) -> bool:
        """Check if a server is responsive."""
        try:
            async with self._session() as session:
                async with session.get(f"{server.url}") as response:
                    is_alive = 200 <= response.status < 300
                    if is_alive:
                        self.logger.debug(f"✨ Health check passed for {server.url} ✨")
                    else:
                        self.logger.debug(f"⚠️  Health check failed for {server.url} with status {response.status} ⚠️")
                    return is_alive
        except Exception as e:
            self.logger.error(f"❌ Health check failed for {server.url}: {str(e)} ❌")
            return False

    async def _start_health_checker(self):
        """Start periodic health checking of all servers."""
        while True:
            for server in self.servers:
                server.is_alive = await self._health_check(server)
                server.last_checked = asyncio.get_event_loop().time()
            await asyncio.sleep(self.health_check_interval)

    async def _get_available_server(self) -> ServerInfo:
        """Get a random available server or raise error if none available."""

        alive_servers = [s for s in self.servers if s.is_alive]
        
        if not alive_servers:
            self.logger.warning("🔄 No alive servers found, performing immediate health check... 🔄")
            for server in self.servers:
                server.is_alive = await self._health_check(server)
                server.last_checked = asyncio.get_event_loop().time()
                if server.is_alive:
                    alive_servers.append(server)
        
        if not alive_servers:
            error_msg = "❌ No Stable Diffusion servers are available."
            self.logger.warning(error_msg)
            raise RuntimeError(error_msg)
            
        selected_server = random.choice(alive_servers)
        self.logger.debug(f"🎯 Selected server: {selected_server.url}")
        return selected_server

    async def _api_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """Make an API request to an available Stable Diffusion server."""
        server = await self._get_available_server()
        
        async with self._session() as session:
            url = f"{server.url}/{endpoint.lstrip('/')}"
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

    async def start(self):
        """Start the client and health checker."""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            self.logger.info("🌟 Created new aiohttp session 🌟")
        
        self.logger.info("🔍 Performing initial health check... 🔍")
        for server in self.servers:
            server.is_alive = await self._health_check(server)
            server.last_checked = asyncio.get_event_loop().time()
        
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._start_health_checker())
            self.logger.info("✅ Started health checker task ✅")

    async def text2img(self, config: Union[SDConfig, Dict[str, Any]]) -> List[bytes]:
        """Generate images from text prompt using Stable Diffusion."""
        if isinstance(config, dict):
            payload = config
        elif isinstance(config, SDConfig):
            payload = config.to_dict()
        else:
            error_msg = "❌ Config must be SDConfig or dict"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info(f"🎨 Generating image with prompt: {payload.get('prompt', '')[:50]}... ✨")
        
        result = await self._api_request(
            "sdapi/v1/txt2img",
            method="POST",
            json=payload
        )
        return [base64.b64decode(img) for img in result["images"]]

    async def get_samplers(self) -> List[Dict[str, str]]:
        """Get list of available samplers.
        
        Returns:
            List[Dict[str, str]]: List of sampler info with name and aliases
            
        Raises:
            aiohttp.ClientError: If API request fails
        """
        return await self._api_request("sdapi/v1/samplers")

    async def get_models(self) -> List[Dict[str, Any]]:
        """Get list of available models.
        
        Returns:
            List[Dict[str, Any]]: List of model info
            
        Raises:
            aiohttp.ClientError: If API request fails
        """
        return await self._api_request("sdapi/v1/sd-models")

    async def close(self) -> None:
        """Close the client session and stop health checker."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            self.logger.info("🛑 Health checker task stopped 🛑")
            
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            self.logger.info("👋 Session closed 👋")

    def __del__(self):
        """Ensure session and tasks are cleaned up on deletion."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
        
        if self.session and not self.session.closed:
            if self.session._loop.is_running():
                self.session._loop.create_task(self.session.close())
            else:
                self.session._loop.run_until_complete(self.session.close())