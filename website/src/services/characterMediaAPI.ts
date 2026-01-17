/**
 * Multi-threaded Media Fetcher for Characters
 * Fetches: Banners, Character Art, GIFs, Screenshots, etc.
 */

export interface CharacterMedia {
  portraits: string[];      // Character portraits/headshots
  fullBody: string[];       // Full body images
  banners: string[];        // Wide banner images
  gifs: string[];          // Animated GIFs
  screenshots: string[];   // Anime screenshots
  fanart: string[];        // High-quality fanart
  official: string[];      // Official artwork
}

/**
 * Tenor GIF API - Animated GIFs
 */
async function fetchGIFs(characterName: string, seriesName: string): Promise<string[]> {
  try {
    const query = `${characterName} ${seriesName} anime`;
    const apiKey = import.meta.env.VITE_TENOR_API_KEY || 'AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ'; // Demo key
    
    const response = await fetch(
      `https://tenor.googleapis.com/v2/search?q=${encodeURIComponent(query)}&key=${apiKey}&limit=20&media_filter=gif&contentfilter=medium`
    );
    
    if (!response.ok) throw new Error('Tenor API failed');
    
    const data = await response.json();
    return data.results?.map((r: any) => r.media_formats.gif.url) || [];
  } catch (error) {
    console.error('[Tenor] GIF fetch failed:', error);
    return [];
  }
}

/**
 * Giphy API - Alternative GIF source
 */
async function fetchGiphyGIFs(characterName: string, seriesName: string): Promise<string[]> {
  try {
    const query = `${characterName} ${seriesName} anime`;
    const apiKey = import.meta.env.VITE_GIPHY_API_KEY || 'dc6zaTOxFJmzC'; // Public beta key
    
    // First try with the API key
    let response = await fetch(
      `https://api.giphy.com/v1/gifs/search?api_key=${apiKey}&q=${encodeURIComponent(query)}&limit=20&rating=pg`
    );
    
    // If we get a 403, try without the API key (some public endpoints work)
    if (response.status === 403) {
      console.warn('[Giphy] API key rejected, trying without key');
      response = await fetch(
        `https://api.giphy.com/v1/gifs/search?q=${encodeURIComponent(query)}&limit=20&rating=pg`
      );
    }
    
    if (!response.ok) {
      throw new Error(`Giphy API failed with status ${response.status}`);
    }
    
    const data = await response.json();
    return data.data?.map((g: any) => g.images.original.url) || [];
  } catch (error) {
    console.error('[Giphy] GIF fetch failed, falling back to Tenor:', error);
    // Fall back to Tenor if Giphy fails
    return fetchGIFs(characterName, seriesName);
  }
}

/**
 * Danbooru - Character portraits and art
 * Note: Danbooru requires proper tag formatting (no spaces, use underscores)
 */
async function fetchDanbooruByType(characterName: string, _seriesName: string, type: string): Promise<string[]> {
  try {
    // Simplify tags - just use character name and type for better results
    const charTag = characterName.toLowerCase().replace(/\s+/g, '_');
    const tags = `${charTag} ${type} rating:safe`;
    
    const response = await fetch(
      `/api/danbooru/posts.json?tags=${encodeURIComponent(tags)}&limit=20`
    );
    
    if (!response.ok) {
      if (response.status !== 422) { // Don't log 422 (invalid tags) as an error
        console.warn(`[Danbooru] API error: ${response.status} ${response.statusText}`);
      }
      return [];
    }
    
    const data = await response.json();
    return data
      .filter((post: any) => post.file_url && post.rating === 's')
      .map((post: any) => post.file_url)
      .slice(0, 10);
  } catch (error) {
    console.error('[Danbooru] Fetch error:', error);
    return [];
  }
}

/**
 * Gelbooru - Safe character images (using proxy)
 */
async function fetchGelbooruByType(characterName: string, _seriesName: string, type: string): Promise<string[]> {
  try {
    const charTag = characterName.toLowerCase().replace(/\s+/g, '_');
    const tags = `${charTag} ${type} rating:safe`;
    
    const response = await fetch(
      `/api/gelbooru/index.php?page=dapi&s=post&q=index&json=1&tags=${encodeURIComponent(tags)}&limit=20`
    );
    
    if (!response.ok) {
      console.warn(`[Gelbooru] API error: ${response.status} ${response.statusText}`);
      return [];
    }
    
    const data = await response.json();
    const posts = data.post || data;
    return (Array.isArray(posts) ? posts : [])
      .filter((post: any) => post.file_url && post.rating === 's')
      .map((post: any) => post.file_url)
      .slice(0, 10);
  } catch (error) {
    console.error('[Gelbooru] Fetch error:', error);
    return [];
  }
}

/**
 * Fetch all media types in parallel (multi-threaded)
 */
export async function fetchCharacterMedia(
  characterName: string,
  seriesName: string
): Promise<CharacterMedia> {
  console.log(`[Media] Fetching all media for ${characterName}...`);
  
  const startTime = Date.now();
  
  // Fetch all types in parallel (multi-threaded)
  const [
    portraits1,
    portraits2,
    fullBody1,
    fullBody2,
    gifs1,
    gifs2,
    fanart1,
    official1
  ] = await Promise.all([
    // Portraits
    fetchDanbooruByType(characterName, seriesName, 'solo'),
    fetchGelbooruByType(characterName, seriesName, 'solo'),
    
    // Full body
    fetchDanbooruByType(characterName, seriesName, 'full_body'),
    fetchGelbooruByType(characterName, seriesName, 'standing'),
    
    // GIFs
    fetchGIFs(characterName, seriesName),
    fetchGiphyGIFs(characterName, seriesName),
    
    // Fanart
    fetchGelbooruByType(characterName, seriesName, 'highres'),
    
    // Official art
    fetchDanbooruByType(characterName, seriesName, 'official_art')
  ]);
  
  const media: CharacterMedia = {
    portraits: [...new Set([...portraits1, ...portraits2])].slice(0, 15),
    fullBody: [...new Set([...fullBody1, ...fullBody2])].slice(0, 15),
    banners: [], // Removed due to CORS issues
    gifs: [...new Set([...gifs1, ...gifs2])].slice(0, 10),
    screenshots: [], // Removed due to CORS issues
    fanart: [...new Set(fanart1)].slice(0, 20),
    official: [...new Set(official1)].slice(0, 10)
  };
  
  const totalImages = Object.values(media).reduce((sum, arr) => sum + arr.length, 0);
  const elapsed = Date.now() - startTime;
  
  console.log(`[Media] Fetched ${totalImages} media items in ${elapsed}ms`);
  
  return media;
}

/**
 * Get media count summary
 */
export function getMediaSummary(media: CharacterMedia): string {
  const total = Object.values(media).reduce((sum, arr) => sum + arr.length, 0);
  return `${total} images (${media.portraits.length} portraits, ${media.gifs.length} GIFs, ${media.banners.length} banners)`;
}
