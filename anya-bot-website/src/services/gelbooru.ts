import axios from 'axios';

const GELBOORU_API_URL = 'https://gelbooru.com/index.php';

interface GelbooruPost {
  id: number;
  file_url: string;
  preview_url: string;
  sample_url: string;
  tags: string;
  rating: 's' | 'q' | 'e';
  score: number;
  width: number;
  height: number;
}

export const searchGelbooru = async (tags: string[], limit: number = 20, page: number = 0): Promise<GelbooruPost[]> => {
  try {
    const params = new URLSearchParams({
      page: 'dapi',
      s: 'post',
      q: 'index',
      json: '1',
      limit: limit.toString(),
      pid: page.toString(),
      tags: [...tags, 'rating:safe'].join(' '),
    });

    const response = await axios.get(`${GELBOORU_API_URL}?${params.toString()}`, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      },
    });

    // Handle both array and object responses
    const posts = Array.isArray(response.data) ? response.data : (response.data.post || []);
    
    return posts.map((post: any) => ({
      id: post.id,
      file_url: post.file_url || '',
      preview_url: post.preview_url || post.sample_url || post.file_url || '',
      sample_url: post.sample_url || post.file_url || '',
      tags: post.tags || '',
      rating: post.rating || 's',
      score: parseInt(post.score || '0'),
      width: parseInt(post.width || '0'),
      height: parseInt(post.height || '0'),
    }));
  } catch (error) {
    console.error('Error searching Gelbooru:', error);
    return [];
  }
};

export const getRandomPost = async (tags: string[] = []): Promise<GelbooruPost | null> => {
  try {
    const posts = await searchGelbooru(tags, 100);
    if (posts.length === 0) return null;
    
    const randomIndex = Math.floor(Math.random() * posts.length);
    return posts[randomIndex];
  } catch (error) {
    console.error('Error getting random Gelbooru post:', error);
    return null;
  }
};

export const getPostsByCharacter = async (characterName: string, limit: number = 10): Promise<GelbooruPost[]> => {
  const formattedName = characterName.toLowerCase().replace(/\s+/g, '_');
  return searchGelbooru([formattedName, 'solo'], limit);
};
