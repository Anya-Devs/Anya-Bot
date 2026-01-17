const BASE_URL = process.env.API_URL || 'http://localhost:3000';

async function testAPI() {
  console.log('🧪 Testing Anime Gacha API...\n');
  
  try {
    console.log('1️⃣ Testing health endpoint...');
    const healthRes = await fetch(`${BASE_URL}/health`);
    const health = await healthRes.json();
    console.log('   ✅ Health:', health.status);
    console.log('   📊 Cache stats:', health.cache?.stats || 'N/A');
    console.log();
    
    console.log('2️⃣ Testing random character (common)...');
    const start1 = Date.now();
    const commonRes = await fetch(`${BASE_URL}/api/characters/random?rarity=common`);
    const common = await commonRes.json();
    console.log(`   ⏱️ Response time: ${Date.now() - start1}ms`);
    console.log(`   ⚪ Got: ${common.name} from ${common.anime}`);
    console.log();
    
    console.log('3️⃣ Testing random character (legendary)...');
    const start2 = Date.now();
    const legendaryRes = await fetch(`${BASE_URL}/api/characters/random?rarity=legendary`);
    const legendary = await legendaryRes.json();
    console.log(`   ⏱️ Response time: ${Date.now() - start2}ms`);
    console.log(`   🟡 Got: ${legendary.name} from ${legendary.anime}`);
    console.log();
    
    console.log('4️⃣ Testing batch fetch (3 characters)...');
    const start3 = Date.now();
    const batchRes = await fetch(`${BASE_URL}/api/characters/batch?count=3&rarities=common,rare,epic`);
    const batch = await batchRes.json();
    console.log(`   ⏱️ Response time: ${Date.now() - start3}ms`);
    console.log(`   📦 Got ${batch.count} characters:`);
    for (const char of batch.characters) {
      const emoji = { legendary: '🟡', epic: '🟣', rare: '🔵', uncommon: '🟢', common: '⚪' }[char.rarity];
      console.log(`      ${emoji} ${char.name} (${char.rarity})`);
    }
    console.log();
    
    console.log('5️⃣ Testing search...');
    const start4 = Date.now();
    const searchRes = await fetch(`${BASE_URL}/api/characters/search?name=naruto&limit=3`);
    const search = await searchRes.json();
    console.log(`   ⏱️ Response time: ${Date.now() - start4}ms`);
    console.log(`   🔍 Found ${search.count} results for "naruto"`);
    for (const char of search.results.slice(0, 3)) {
      console.log(`      - ${char.name} from ${char.anime}`);
    }
    console.log();
    
    console.log('6️⃣ Testing stats endpoint...');
    const statsRes = await fetch(`${BASE_URL}/api/characters/stats`);
    const stats = await statsRes.json();
    console.log('   📊 Character counts by rarity:');
    console.log(`      🟡 Legendary: ${stats.legendary}`);
    console.log(`      🟣 Epic: ${stats.epic}`);
    console.log(`      🔵 Rare: ${stats.rare}`);
    console.log(`      🟢 Uncommon: ${stats.uncommon}`);
    console.log(`      ⚪ Common: ${stats.common}`);
    console.log(`      📦 Total: ${stats.total}`);
    console.log();
    
    console.log('7️⃣ Speed test (10 rapid requests)...');
    const start5 = Date.now();
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(fetch(`${BASE_URL}/api/characters/random?rarity=common`));
    }
    await Promise.all(promises);
    const avgTime = (Date.now() - start5) / 10;
    console.log(`   ⚡ Average response time: ${avgTime.toFixed(2)}ms`);
    console.log();
    
    console.log('✅ All tests passed!');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  }
}

testAPI();
