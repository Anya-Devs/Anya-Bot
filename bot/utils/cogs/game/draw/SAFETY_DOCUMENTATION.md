# Cover Art System - Safety Documentation

## 🛡️ MAXIMUM SAFETY STANDARDS FOR ALL-AGES BOT

This bot is designed to be **100% family-friendly** and safe for all ages. We take content safety extremely seriously to ensure compliance with Discord TOS and provide a wholesome experience.

---

## 🔒 Multi-Layer Safety System

### Layer 1: Source Selection
**ONLY Safe-Rated Sources:**
- ✅ **Safebooru.org** - Dedicated SFW anime image board
- ✅ **Konachan.net** - Safe-rated anime art with strict filters
- ✅ **Danbooru** - Using `rating:general` (strictest rating only)

### Layer 2: Query-Level Filtering
**API Search Filters:**
- Danbooru: `rating:general` + 25+ excluded tags in query
- Konachan: `rating:safe` + 25+ excluded tags in query
- Safebooru: Inherently safe (no additional filters needed)

### Layer 3: Post-Processing Filtering
**150+ Comprehensive Blocked Tags:**

#### Explicit/Sexual Content
- suggestive, ecchi, lewd, nsfw, erotic, sexual, sexy, seductive, provocative, revealing, skimpy, fanservice, risque, sensual, alluring, tempting, sultry, flirtatious, arousing, titillating, indecent

#### Underwear/Intimate Apparel
- panties, underwear, bra, lingerie, bikini, swimsuit, thong, g-string, garter_belt, stockings, garter, negligee, corset, bustier, teddy, panty, brassiere, undergarment, intimate_apparel

#### Sexualized Body Parts/Focus
- cleavage, underboob, sideboob, breast_grab, breasts, boobs, chest, ass, butt, buttocks, rear, behind, thighs, legs, midriff, navel, belly, stomach, hips, waist, curves, figure, body, physique, cleavage_cutout, breast_focus, butt_focus, thigh_focus, leg_focus

#### Suggestive Poses/Actions
- pantyshot, upskirt, cameltoe, spread_legs, legs_apart, straddling, groping, grabbing, touching, breast_hold, arm_under_breasts, squeezing, fondling, caressing, embracing, hugging, cuddling, holding, pinching, spanking, slapping, kneeling, crawling, bending, arching, stretching, lying, reclining, lounging, sitting, on_back, on_stomach, on_side

#### Nudity/Exposure
- nipples, nude, naked, topless, bottomless, barefoot, bare_shoulders, bare_legs, bare_arms, bare_back, bare_chest, bare_midriff, exposed, undressing, undressed, partially_clothed, barely_clothed, scantily_clad, skin_tight, body_suit, leotard, one-piece, two-piece

#### ⚠️ CRITICAL - Discord TOS Protection
- **loli, shota, lolicon, shotacon, young, child, underage, minor**
- bondage, bdsm, chains, rope, tied, restrained, bound, cuffed, collar, leash, gag, blindfold, submissive, dominant, slave, master

#### Suggestive Clothing States
- bath, bathing, shower, showering, bathtub, onsen, hot_spring, wet, wet_clothes, soaked, drenched, dripping, sweaty, sweat, see-through, transparent, translucent, sheer, mesh, fishnet, tight, tight_clothes, form-fitting, skin_tight, clingy, hugging, torn_clothes, ripped, damaged, wardrobe_malfunction, clothing_aside, dress_lift, skirt_lift, shirt_lift, lifted_by_self, wind_lift

#### Voyeuristic Angles/Camera Focus
- from_below, from_behind, back_view, rear_view, side_view, profile, butt_focus, breast_focus, crotch, between_legs, pov, close-up, looking_at_viewer, eye_contact, seductive_gaze, bedroom_eyes, over_shoulder, looking_back, head_tilt, wink, blush

#### Bedroom/Private Settings
- bed, bedroom, pillow, sheets, blanket, lying_on_bed, in_bed, hotel, love_hotel, motel, room, private, alone, intimate

#### Romantic/Sexual Situations
- kiss, kissing, making_out, french_kiss, lip_lock, embrace, couple, lovers, romance, romantic, love, affection, intimate, date, dating, valentine, heart, hearts, love_letter

#### Misc Inappropriate
- mature, adult, r-15, r-18, r18, rating:questionable, rating:explicit, censored, uncensored, mosaic, convenient_censoring, steam, steam_censor, ahegao, orgasm, pleasure, aroused, flushed, embarrassed, shy, naughty, mischievous, playful, teasing, tease, temptation

### Layer 4: URL Validation
**Image URL Verification:**
- Valid image extensions (.jpg, .jpeg, .png, .gif, .webp)
- Trusted hosts only (safebooru.org, konachan.net, danbooru.donmai.us)
- Format validation before caching

### Layer 5: Rating Enforcement
**Strict Rating Checks:**
- Danbooru: Only `'g'` (general) rating accepted
- Konachan: Only `'s'` (safe) rating accepted
- Safebooru: Inherently safe-rated

---

## 🎯 What Gets Through?

**ONLY wholesome, family-friendly anime fan art:**
- Character portraits (fully clothed)
- Action scenes
- Cute/chibi art
- Landscape/scenery with characters
- Group shots
- Cosplay (appropriate)
- Official anime art style
- Fan art (non-suggestive)

---

## ❌ What Gets Blocked?

**EVERYTHING inappropriate including:**
- Any sexualized content
- Suggestive poses or angles
- Revealing clothing
- Beach/swimsuit content
- Romantic/intimate scenes
- Any loli/shota content (Discord TOS violation)
- Softcore or borderline content
- Fanservice imagery

---

## 📊 Safety Statistics

- **150+ blocked tags** across all categories
- **3 independent sources** with safe ratings
- **5 layers of filtering** before display
- **Zero tolerance** policy for inappropriate content
- **100% Discord TOS compliant**

---

## 🔧 Technical Implementation

### Files Modified:
- `multisearch.py` - Core search and filtering logic
- `cover_gallery_view.py` - UI and pagination
- `cover_art.py` - Integration layer

### Key Functions:
- `_search_danbooru_safe_only()` - Danbooru with maximum safety
- `_search_konachan()` - Konachan with safe filters
- `_search_safebooru_org()` - Primary safe source
- `_process_*_results()` - Post-processing filters
- `_is_valid_image_url()` - URL validation

---

## 🎮 For Bot Administrators

**This bot is safe for:**
- All-ages Discord servers
- Family-friendly communities
- Public servers with minors
- Educational/school servers
- Professional anime communities

**Content Policy:**
Your favorite anime characters will NEVER be sexually glorified or shown in inappropriate contexts. We ensure wholesome, respectful fan art only.

---

## 📝 Maintenance Notes

If you need to add more blocked tags:
1. Add to the `blocked_tags` set in both `_process_danbooru_safe_results()` and `_process_konachan_results()`
2. Consider adding to query-level blacklist in search functions
3. Test with various character searches
4. Document changes in this file

---

**Last Updated:** January 3, 2026
**Safety Level:** MAXIMUM (All-Ages)
**Discord TOS Compliance:** ✅ FULL
