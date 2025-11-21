import axios from 'axios';
import * as cheerio from 'cheerio';

/**
 * Image scraper using multiple sources
 */
export class ImageScraper {
  constructor() {
    this.sources = [
      { name: 'Google Images', scraper: this.scrapeGoogleImages.bind(this) },
      { name: 'Bing Images', scraper: this.scrapeBingImages.bind(this) },
      { name: 'Danbooru', scraper: this.scrapeDanbooru.bind(this) },
      { name: 'Safebooru', scraper: this.scrapeSafebooru.bind(this) }
    ];
  }

  /**
   * Search images from all sources
   */
  async searchImages(browser, query, limit = 50) {
    const allImages = [];
    
    for (const source of this.sources) {
      try {
        console.log(`    - Scraping from ${source.name}...`);
        const images = await source.scraper(browser, query, limit);
        allImages.push(...images);
      } catch (error) {
        console.warn(`    ⚠️  Failed to scrape ${source.name}:`, error.message);
      }
    }
    
    return allImages;
  }

  /**
   * Scrape Google Images using Puppeteer
   */
  async scrapeGoogleImages(browser, query, limit = 30) {
    const page = await browser.newPage();
    const images = [];
    
    try {
      await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
      
      const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(query)}&tbm=isch`;
      await page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 30000 });
      
      // Scroll to load more images
      for (let i = 0; i < 3; i++) {
        await page.evaluate(() => window.scrollBy(0, window.innerHeight));
        await this.delay(500);
      }
      
      // Extract image URLs
      const imageElements = await page.$$('img');
      
      for (const img of imageElements) {
        if (images.length >= limit) break;
        
        try {
          const src = await img.evaluate(el => el.src);
          const alt = await img.evaluate(el => el.alt);
          
          if (src && src.startsWith('http') && !src.includes('google.com/images/branding')) {
            images.push({
              url: src,
              source: 'Google Images',
              alt: alt || query,
              width: await img.evaluate(el => el.naturalWidth),
              height: await img.evaluate(el => el.naturalHeight)
            });
          }
        } catch (e) {
          // Skip invalid images
        }
      }
      
    } catch (error) {
      console.error('Google Images scraping error:', error.message);
    } finally {
      await page.close();
    }
    
    return images;
  }

  /**
   * Scrape Bing Images
   */
  async scrapeBingImages(browser, query, limit = 30) {
    const page = await browser.newPage();
    const images = [];
    
    try {
      await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
      
      const searchUrl = `https://www.bing.com/images/search?q=${encodeURIComponent(query)}`;
      await page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 30000 });
      
      // Scroll to load more
      for (let i = 0; i < 3; i++) {
        await page.evaluate(() => window.scrollBy(0, window.innerHeight));
        await this.delay(500);
      }
      
      // Extract image data from Bing's structure
      const imageData = await page.evaluate(() => {
        const imgs = [];
        document.querySelectorAll('.iusc').forEach(el => {
          try {
            const m = JSON.parse(el.getAttribute('m'));
            if (m && m.murl) {
              imgs.push({
                url: m.murl,
                thumbnail: m.turl,
                width: m.width,
                height: m.height,
                title: m.t
              });
            }
          } catch (e) {}
        });
        return imgs;
      });
      
      images.push(...imageData.slice(0, limit).map(img => ({
        ...img,
        source: 'Bing Images',
        alt: img.title || query
      })));
      
    } catch (error) {
      console.error('Bing Images scraping error:', error.message);
    } finally {
      await page.close();
    }
    
    return images;
  }

  /**
   * Scrape Danbooru (anime image board)
   */
  async scrapeDanbooru(browser, query, limit = 20) {
    try {
      const tags = query.toLowerCase().replace(/\s+/g, '_');
      const url = `https://danbooru.donmai.us/posts.json?tags=${encodeURIComponent(tags)}&limit=${limit}`;
      
      const response = await axios.get(url, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        timeout: 10000
      });
      
      return response.data.map(post => ({
        url: post.file_url,
        source: 'Danbooru',
        alt: post.tag_string,
        width: post.image_width,
        height: post.image_height,
        rating: post.rating,
        score: post.score
      })).filter(img => img.url && img.rating === 's'); // Only safe images
      
    } catch (error) {
      console.error('Danbooru scraping error:', error.message);
      return [];
    }
  }

  /**
   * Scrape Safebooru (safe anime images only)
   */
  async scrapeSafebooru(browser, query, limit = 20) {
    try {
      const tags = query.toLowerCase().replace(/\s+/g, '_');
      const url = `https://safebooru.org/index.php?page=dapi&s=post&q=index&tags=${encodeURIComponent(tags)}&limit=${limit}`;
      
      const response = await axios.get(url, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        timeout: 10000
      });
      
      const $ = cheerio.load(response.data, { xmlMode: true });
      const images = [];
      
      $('post').each((i, el) => {
        const $el = $(el);
        images.push({
          url: `https:${$el.attr('file_url')}`,
          source: 'Safebooru',
          alt: $el.attr('tags'),
          width: parseInt($el.attr('width')),
          height: parseInt($el.attr('height')),
          score: parseInt($el.attr('score'))
        });
      });
      
      return images;
      
    } catch (error) {
      console.error('Safebooru scraping error:', error.message);
      return [];
    }
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
