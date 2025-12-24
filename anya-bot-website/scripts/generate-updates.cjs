const fs = require('fs');
const path = require('path');

const CACHE_FILE = path.join(__dirname, '../.feature-cache.json');
const SRC_DIR = path.join(__dirname, '../src');

function getLastModified(filePath) {
  try {
    const stats = fs.statSync(filePath);
    return stats.mtime.toISOString();
  } catch {
    return new Date().toISOString();
  }
}

function scanDirectory(dir, ext) {
  const files = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        files.push(...scanDirectory(fullPath, ext));
      } else if (entry.name.endsWith(ext)) {
        files.push(fullPath);
      }
    }
  } catch {
    // Directory doesn't exist or can't be read
  }
  return files;
}

function scanFeatures() {
  const features = {};
  const pagesDir = path.join(SRC_DIR, 'pages');
  const componentsDir = path.join(SRC_DIR, 'components');
  
  // Scan pages
  if (fs.existsSync(pagesDir)) {
    const pageFiles = fs.readdirSync(pagesDir).filter(f => f.endsWith('.tsx'));
    pageFiles.forEach(file => {
      const name = file.replace('.tsx', '');
      features[name] = {
        lastModified: getLastModified(path.join(pagesDir, file))
      };
    });
  }
  
  // Scan components
  if (fs.existsSync(componentsDir)) {
    const componentFiles = fs.readdirSync(componentsDir).filter(f => f.endsWith('.tsx'));
    componentFiles.forEach(file => {
      const name = file.replace('.tsx', '');
      features[name] = {
        lastModified: getLastModified(path.join(componentsDir, file))
      };
    });
  }
  
  return features;
}

function updateCache() {
  let cache = {
    commands: {},
    features: {},
    lastScan: new Date().toISOString()
  };

  // Load existing cache if it exists
  if (fs.existsSync(CACHE_FILE)) {
    try {
      const existing = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf-8'));
      cache.commands = existing.commands || {};
    } catch {
      // Invalid JSON, start fresh
    }
  }

  // Update features
  cache.features = scanFeatures();
  cache.lastScan = new Date().toISOString();

  // Write cache
  fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2));
  console.log('✓ Feature cache updated');
}

updateCache();
