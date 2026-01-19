"""
Anya Image API Client
Ultra-fast client for the Node.js image search API
"""

import aiohttp
import logging
import os
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Support both local and remote API
# Set IMAGE_API_URL environment variable for production
API_BASE_URL = os.getenv("IMAGE_API_URL", "http://localhost:3456")


class ImageAPIClient:
    """Client for the Anya Image API"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = API_BASE_URL
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            # MASS PRODUCTION: No timeout, let API run as fast as it can
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None)
            )
        return self.session
    
    async def search(
        self, 
        character: str, 
        series: str = None, 
        page: int = 1, 
        limit: int = 100
    ) -> Tuple[List[Dict], int]:
        """
        Search for images via the API
        
        Returns:
            Tuple of (images list, max_pages)
        """
        session = await self.get_session()
        
        params = {
            'character': character,
            'page': page,
            'limit': limit
        }
        if series:
            params['series'] = series
        
        try:
            url = f"{self.base_url}/api/search"
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    if data.get('success'):
                        images = data.get('images', [])
                        max_pages = data.get('maxPages', 1)
                        total = data.get('totalImages', 0)
                        timing = data.get('timing', 0)
                        cached = data.get('cached', False)
                        
                        logger.info(
                            f"[API Client] {character}: {len(images)} images, "
                            f"page {page}/{max_pages}, total {total}, "
                            f"{'cached' if cached else f'{timing}ms'}"
                        )
                        
                        # Convert to expected format
                        processed = []
                        for img in images:
                            processed.append({
                                'id': img.get('id'),
                                'url': img.get('url') or img.get('preview'),
                                'preview_url': img.get('preview') or img.get('url'),
                                'file_url': img.get('url'),
                                'width': img.get('width', 0),
                                'height': img.get('height', 0),
                                'score': img.get('score', 0),
                                'tags': img.get('tags', []),
                                'source': img.get('source', 'Unknown')
                            })
                        
                        return processed, max_pages
                    else:
                        logger.error(f"[API Client] API error: {data.get('error')}")
                else:
                    logger.error(f"[API Client] HTTP {resp.status}")
        except aiohttp.ClientConnectorError:
            logger.error("[API Client] Cannot connect to API - is it running?")
        except Exception as e:
            logger.error(f"[API Client] Error: {e}")
        
        return [], 1
    
    async def get_tags(self, character: str, series: str = None) -> Dict[str, str]:
        """Get discovered tags for a character"""
        session = await self.get_session()
        
        params = {'character': character}
        if series:
            params['series'] = series
        
        try:
            url = f"{self.base_url}/api/tags"
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('tags', {})
        except Exception as e:
            logger.error(f"[API Client] Tags error: {e}")
        
        return {}
    
    async def health_check(self) -> bool:
        """Check if API is running"""
        session = await self.get_session()
        
        try:
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except:
            return False
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


# Singleton instance
_client: Optional[ImageAPIClient] = None


def get_api_client() -> ImageAPIClient:
    global _client
    if _client is None:
        _client = ImageAPIClient()
    return _client
