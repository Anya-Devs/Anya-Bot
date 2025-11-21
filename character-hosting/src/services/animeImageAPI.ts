/**
 * Anime Image Search API Integration
 * Supports multiple anime-specific image sources
 */

export interface ImageSearchResult {
  url: string;
  thumbnail: string;
  source: string;
  width: number;
  height: number;
  rating: 'safe' | 'questionable' | 'explicit';
  tags: string[];
}

/**
 * Danbooru API - Large anime image database
 * Free API, no key required
 */
export async function searchDanbooru(tags: string[], limit: number = 20): Promise<ImageSearchResult[]> {
  try {
    const tagString = tags.join(' ').toLowerCase();
    const url = `https://danbooru.donmai.us/posts.json?tags=${encodeURIComponent(tagString)}&limit=${limit}&only=id,file_url,preview_file_url,image_width,image_height,rating,tag_string`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Danbooru API failed');
    
    const data = await response.json();
    
    return data
      .filter((post: any) => post.file_url) // Only posts with images
      .map((post: any) => ({
        url: post.file_url,
        thumbnail: post.preview_file_url || post.file_url,
        source: 'danbooru',
        width: post.image_width || 0,
        height: post.image_height || 0,
        rating: post.rating === 's' ? 'safe' : post.rating === 'q' ? 'questionable' : 'explicit',
        tags: post.tag_string?.split(' ') || []
      }));
  } catch (error) {
    console.error('Danbooru search failed:', error);
    return [];
  }
}

/**
 * Safebooru API - Safe-for-work anime images only
 * No API key required
 */
export async function searchSafebooru(tags: string[], limit: number = 20): Promise<ImageSearchResult[]> {
  try {
    const tagString = tags.join(' ').toLowerCase();
    const url = `https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=${encodeURIComponent(tagString)}&limit=${limit}`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Safebooru API failed');
    
    const data = await response.json();
    
    return (Array.isArray(data) ? data : [])
      .filter((post: any) => post.image)
      .map((post: any) => ({
        url: `https://safebooru.org/images/${post.directory}/${post.image}`,
        thumbnail: `https://safebooru.org/thumbnails/${post.directory}/thumbnail_${post.image}`,
        source: 'safebooru',
        width: parseInt(post.width) || 0,
        height: parseInt(post.height) || 0,
        rating: 'safe',
        tags: post.tags?.split(' ') || []
      }));
  } catch (error) {
    console.error('Safebooru search failed:', error);
    return [];
  }
}

/**
 * Gelbooru API - Large anime image database
 * No API key required for basic usage
 */
export async function searchGelbooru(tags: string[], limit: number = 20): Promise<ImageSearchResult[]> {
  try {
    const tagString = tags.join(' ').toLowerCase();
    const url = `https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags=${encodeURIComponent(tagString)}&limit=${limit}`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Gelbooru API failed');
    
    const data = await response.json();
    const posts = data.post || [];
    
    return (Array.isArray(posts) ? posts : [])
      .filter((post: any) => post.file_url)
      .map((post: any) => ({
        url: post.file_url,
        thumbnail: post.preview_url || post.file_url,
        source: 'gelbooru',
        width: parseInt(post.width) || 0,
        height: parseInt(post.height) || 0,
        rating: post.rating === 's' ? 'safe' : post.rating === 'q' ? 'questionable' : 'explicit',
        tags: post.tags?.split(' ') || []
      }));
  } catch (error) {
    console.error('Gelbooru search failed:', error);
    return [];
  }
}

/**
 * Search multiple sources and combine results
 */
export async function searchAllSources(
  characterName: string,
  seriesName: string,
  options: {
    safeOnly?: boolean;
    minWidth?: number;
    minHeight?: number;
    maxResults?: number;
  } = {}
): Promise<ImageSearchResult[]> {
  const {
    safeOnly = true,
    minWidth = 400,
    minHeight = 400,
    maxResults = 30
  } = options;

  // Build search tags
  const tags = [
    characterName.toLowerCase().replace(/\s+/g, '_'),
    seriesName.toLowerCase().replace(/\s+/g, '_')
  ];

  // Search all sources in parallel
  const searches = safeOnly 
    ? [searchSafebooru(tags, maxResults)]
    : [
        searchDanbooru(tags, maxResults),
        searchSafebooru(tags, maxResults),
        searchGelbooru(tags, maxResults)
      ];

  const results = await Promise.all(searches);
  const allImages = results.flat();

  // Filter and deduplicate
  const filtered = allImages
    .filter(img => 
      img.width >= minWidth &&
      img.height >= minHeight &&
      (safeOnly ? img.rating === 'safe' : true)
    );

  // Deduplicate by URL
  const uniqueUrls = new Set<string>();
  const unique = filtered.filter(img => {
    if (uniqueUrls.has(img.url)) return false;
    uniqueUrls.add(img.url);
    return true;
  });

  return unique.slice(0, maxResults);
}

/**
 * Get character image with fallback sources
 */
export async function getCharacterImages(
  characterName: string,
  seriesName: string,
  count: number = 10
): Promise<string[]> {
  const results = await searchAllSources(characterName, seriesName, {
    safeOnly: true,
    maxResults: count * 2 // Get extra in case some fail
  });

  return results.slice(0, count).map(r => r.url);
}
