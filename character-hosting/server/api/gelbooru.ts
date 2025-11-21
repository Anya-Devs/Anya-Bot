import express from 'express';
import { searchGelbooru, getRandomPost, getPostsByCharacter } from '../../src/services/gelbooru';

const router = express.Router();

// Enable CORS for all routes
router.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// Search endpoint
router.get('/search', async (req, res) => {
  try {
    const { tags = '', limit = 20, page = 0 } = req.query;
    const tagArray = typeof tags === 'string' ? tags.split(' ').filter(Boolean) : [];
    const results = await searchGelbooru(tagArray, Number(limit), Number(page));
    res.json(results);
  } catch (error) {
    console.error('Error in Gelbooru search:', error);
    res.status(500).json({ error: 'Failed to search Gelbooru' });
  }
});

// Random post endpoint
router.get('/random', async (req, res) => {
  try {
    const { tags = '' } = req.query;
    const tagArray = typeof tags === 'string' ? tags.split(' ').filter(Boolean) : [];
    const post = await getRandomPost(tagArray);
    
    if (!post) {
      return res.status(404).json({ error: 'No posts found' });
    }
    
    res.json(post);
  } catch (error) {
    console.error('Error getting random Gelbooru post:', error);
    res.status(500).json({ error: 'Failed to get random post' });
  }
});

// Get posts by character name
router.get('/character/:name', async (req, res) => {
  try {
    const { name } = req.params;
    const { limit = 10 } = req.query;
    const posts = await getPostsByCharacter(name, Number(limit));
    res.json(posts);
  } catch (error) {
    console.error('Error getting character posts:', error);
    res.status(500).json({ error: 'Failed to get character posts' });
  }
});

// Direct API proxy for index.php requests (used by multiSourceImageAPI)
router.get('/index.php', async (req, res) => {
  try {
    const { page = 'dapi', s = 'post', q = 'index', json = '1', tags, limit = 20 } = req.query;

    // Build Gelbooru API URL
    const baseUrl = 'https://gelbooru.com/index.php';
    const params = new URLSearchParams({
      page: page as string,
      s: s as string,
      q: q as string,
      json: json as string,
      tags: tags as string,
      limit: limit as string
    });

    const apiUrl = `${baseUrl}?${params.toString()}`;

    console.log(`[Gelbooru API] Fetching: ${apiUrl}`);

    const response = await fetch(apiUrl, {
      headers: {
        'User-Agent': 'Anya-Bot-Character-Hosting/1.0',
        'Accept': 'application/json'
      },
      signal: AbortSignal.timeout(10000)
    });

    console.log(`[Gelbooru API] Response status: ${response.status}`);

    if (!response.ok) {
      console.error(`[Gelbooru API] Failed with status ${response.status}: ${response.statusText}`);
      // Return empty results for auth/rate limit issues
      if (response.status === 401 || response.status === 403) {
        console.log('[Gelbooru API] Authentication issue, returning empty results');
        return res.json({ post: [] });
      }
      throw new Error(`Gelbooru API returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[Gelbooru API] Successfully fetched ${data.post?.length || 0} posts`);
    res.json(data);
  } catch (error) {
    console.error('Error in Gelbooru API:', error);
    res.json({ post: [] });
  }
});

export default router;
