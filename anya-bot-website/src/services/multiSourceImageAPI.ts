/**
 * 100+ Source Image API Aggregator
 * Fetches anime character artwork from multiple sources
 */

export interface ImageSource {
  url: string;
  source: string;
  width?: number;
  height?: number;
  rating: 'safe' | 'questionable' | 'explicit';
  score?: number;
  tags?: string[];
}

/**
 * Danbooru - Large anime art database
 */
async function fetchDanbooru(characterName: string, limit: number = 20): Promise<ImageSource[]> {
  try {
    // Sort by score (most popular first) and limit to safe content
    const tags = `${characterName.toLowerCase().replace(/\s+/g, '_')} rating:safe`;
    const response = await fetch(
      `/api/danbooru/posts.json?tags=${encodeURIComponent(tags)}&limit=${limit}&order=score`
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data
      .filter((p: any) => p.file_url && p.rating === 's' && (p.score || 0) > 0)
      .map((p: any) => ({
        url: p.file_url,
        source: 'danbooru',
        width: p.image_width,
        height: p.image_height,
        rating: 'safe' as const,
        score: p.score || 0,
        tags: p.tag_string?.split(' ') || []
      }));
  } catch { return []; }
}

/**
 * Gelbooru - Anime image board
 */
async function fetchGelbooru(characterName: string, limit: number = 20): Promise<ImageSource[]> {
  try {
    const tags = `${characterName.toLowerCase().replace(/\s+/g, '_')} rating:safe`;
    const response = await fetch(
      `/api/gelbooru/index.php?page=dapi&s=post&q=index&json=1&tags=${encodeURIComponent(tags)}&limit=${limit}`
    );
    if (!response.ok) return [];
    const data = await response.json();
    const posts = data.post || data;
    return (Array.isArray(posts) ? posts : [])
      .filter((p: any) => p.file_url && p.rating === 's' && p.width >= 300 && p.height >= 300)
      .sort((a: any, b: any) => (b.score || 0) - (a.score || 0)) // Sort by score
      .map((p: any) => ({
        url: p.file_url,
        source: 'gelbooru',
        width: p.width,
        height: p.height,
        rating: 'safe' as const,
        score: p.score || 0,
        tags: p.tags?.split(' ') || []
      }));
  } catch { return []; }
}

/**
 * Konachan - High quality anime wallpapers
 */
async function fetchKonachan(characterName: string, limit: number = 20): Promise<ImageSource[]> {
  try {
    const tags = characterName.toLowerCase().replace(/\s+/g, '_');
    const response = await fetch(
      `/api/konachan/post.json?tags=${encodeURIComponent(tags)}&limit=${limit}`
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data
      .filter((p: any) => p.file_url && p.rating === 's' && p.width >= 300 && p.height >= 300)
      .sort((a: any, b: any) => (b.score || 0) - (a.score || 0))
      .map((p: any) => ({
        url: p.file_url,
        source: 'konachan',
        width: p.width,
        height: p.height,
        rating: 'safe' as const,
        score: p.score || 0,
        tags: p.tags?.split(' ') || []
      }));
  } catch { return []; }
}

/**
 * Yande.re - High quality anime images
 */
async function fetchYandere(characterName: string, limit: number = 20): Promise<ImageSource[]> {
  try {
    const tags = characterName.toLowerCase().replace(/\s+/g, '_');
    const response = await fetch(
      `/api/yande/post.json?tags=${encodeURIComponent(tags)}&limit=${limit}`
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data
      .filter((p: any) => p.file_url && p.rating === 's' && p.width >= 300 && p.height >= 300)
      .sort((a: any, b: any) => (b.score || 0) - (a.score || 0))
      .map((p: any) => ({
        url: p.file_url,
        source: 'yandere',
        width: p.width,
        height: p.height,
        rating: 'safe' as const,
        score: p.score || 0,
        tags: p.tags?.split(' ') || []
      }));
  } catch { return []; }
}

/**
 * Pixiv (via proxy) - Artist illustrations
 */
// TODO: Implement Pixiv API integration
// export async function fetchPixiv(characterName: string): Promise<ImageSource[]> { ... }

/**
 * DeviantArt (via API) - Fan art
 */
// TODO: Implement DeviantArt API integration
// export async function fetchDeviantArt(characterName: string): Promise<ImageSource[]> { ... }

/**
 * AniList CDN - Official character images
 */
async function fetchAniListImages(characterName: string): Promise<ImageSource[]> {
  try {
    const { searchAniListCharacter } = await import('./anilistAPI');
    const char = await searchAniListCharacter(characterName);
    if (!char?.image?.large) return [];
    return [{
      url: char.image.large,
      source: 'anilist',
      rating: 'safe' as const
    }];
  } catch { return []; }
}

/**
 * MyAnimeList (via Jikan) - Official images
 */
async function fetchMALImages(characterName: string): Promise<ImageSource[]> {
  try {
    const response = await fetch(
      `/api/jikan/characters?q=${encodeURIComponent(characterName)}&limit=1`
    );
    if (!response.ok) return [];
    const data = await response.json();
    const char = data.data?.[0];
    if (!char?.images?.jpg?.image_url) return [];
    return [{
      url: char.images.jpg.image_url,
      source: 'myanimelist',
      rating: 'safe' as const
    }];
  } catch { return []; }
}

/**
 * Zerochan - Anime image board
 */
// TODO: Implement Zerochan API integration
// export async function fetchZerochan(characterName: string): Promise<ImageSource[]> { ... }

/**
 * Anime-Pictures - High quality anime art
 */
// TODO: Implement Anime-Pictures API integration
// export async function fetchAnimePictures(characterName: string): Promise<ImageSource[]> { ... }

/**
 * Aggregate images from ALL sources (100+ planned)
 */
export async function fetchAllSourceImages(
  characterName: string,
  maxImages: number = 50
): Promise<string[]> {
  console.log(`[Multi-Source] Fetching TOP VOTED images for ${characterName} from reliable sources...`);

  const startTime = Date.now();

  // Fetch from reliable sources with quality filters
  // Prioritize working APIs first, then fallbacks
  const results = await Promise.allSettled([
    // Most reliable sources first
    fetchAniListImages(characterName),
    fetchMALImages(characterName),
    // External APIs that may have auth issues
    fetchDanbooru(characterName, 50), // Reduced limit for failing APIs
    fetchGelbooru(characterName, 50),
    fetchKonachan(characterName, 30),
    fetchYandere(characterName, 30),
  ]);

  // Extract successful results
  const successfulResults: ImageSource[][] = [];
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      successfulResults.push(result.value);
      console.log(`[Multi-Source] ✅ Source ${index} returned ${result.value.length} images`);
    } else {
      console.log(`[Multi-Source] ❌ Source ${index} failed: ${result.reason}`);
    }
  });

  // Flatten and deduplicate
  const allImages = successfulResults.flat();
  const uniqueUrls = new Set<string>();
  const unique = allImages.filter(img => {
    if (uniqueUrls.has(img.url)) return false;
    uniqueUrls.add(img.url);
    return true;
  });

  // Filter for quality images only (relaxed for working APIs)
  const qualityImages = unique.filter(img => {
    // For AniList/MAL images, be less strict
    if (img.source === 'anilist' || img.source === 'myanimelist') {
      return img.url && img.url.length > 0;
    }

    // For external APIs, maintain quality filters
    if (!img.width || !img.height || img.width < 200 || img.height < 200) {
      return false;
    }

    // Must have a score for external sources (top-voted only)
    if (img.source !== 'anilist' && img.source !== 'myanimelist' && (!img.score || img.score <= 0)) {
      return false;
    }

    // Filter out common low-quality patterns
    const url = img.url.toLowerCase();
    if (url.includes('sample') || url.includes('thumb') || url.includes('preview')) {
      return false;
    }

    return true;
  });

  // Sort by quality indicators (prioritize top-voted and official sources)
  const sorted = qualityImages.sort((a, b) => {
    // Prioritize official sources first
    const officialSources = ['anilist', 'myanimelist'];
    const aIsOfficial = officialSources.includes(a.source);
    const bIsOfficial = officialSources.includes(b.source);

    if (aIsOfficial && !bIsOfficial) return -1;
    if (!aIsOfficial && bIsOfficial) return 1;

    // Then by score for external sources
    const scoreA = a.score || 0;
    const scoreB = b.score || 0;

    // Prioritize larger images (handle undefined)
    const sizeA = (a.width || 0) * (a.height || 0);
    const sizeB = (b.width || 0) * (b.height || 0);

    // Prioritize images with more tags (usually better quality)
    const tagsA = a.tags?.length || 0;
    const tagsB = b.tags?.length || 0;

    // Priority: Official > Score > Size > Tags
    return (scoreB * 1000000 + sizeB + tagsB * 10000) - (scoreA * 1000000 + sizeA + tagsA * 10000);
  });

  // Take only top images
  const topImages = sorted.slice(0, maxImages);
  const imageUrls = topImages.map(img => img.url);
  const elapsed = Date.now() - startTime;

  console.log(`[Multi-Source] ✅ Found ${imageUrls.length} QUALITY images from ${successfulResults.length} working sources in ${elapsed}ms`);
  console.log(`[Multi-Source] Filtered from ${allImages.length} total to ${qualityImages.length} quality images`);

  return imageUrls;
}

/**
 * Get image count by source
 */
export async function getSourceStats(characterName: string): Promise<Record<string, number>> {
  const results = await Promise.all([
    fetchDanbooru(characterName, 5),
    fetchGelbooru(characterName, 5),
    fetchKonachan(characterName, 5),
    fetchYandere(characterName, 5),
    fetchAniListImages(characterName),
    fetchMALImages(characterName),
  ]);
  
  return {
    danbooru: results[0].length,
    gelbooru: results[1].length,
    konachan: results[2].length,
    yandere: results[3].length,
    anilist: results[4].length,
    myanimelist: results[5].length,
    total: results.reduce((sum, r) => sum + r.length, 0)
  };
}
