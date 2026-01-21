# Cover Art Duplicate Detection & Hash Generation

## Overview
Implemented automatic duplicate detection and hash generation for the `.draw covers` command. The system now:
1. **Generates hashes** for images that don't have one
2. **Scans for duplicates** using image hashes
3. **Automatically removes** duplicate cover art from user inventories

## Changes Made

### 1. Hash Extraction from API Sources (`multisearch.py`)
Updated all image processing methods to extract MD5 hashes from API responses:

- **Danbooru**: Extracts `md5` field
- **Safebooru**: Extracts `hash` or `md5` field
- **Konachan**: Extracts `md5` field
- **Gelbooru**: Extracts `md5` or `hash` field
- **Yande.re**: Extracts `md5` field
- **TBIB**: Extracts `md5` or `hash` field
- **Anime-Pictures**: Already uses `md5` for URLs
- **Tumblr**: Generates hash from URL using MD5

All processed image results now include a `hash` field for duplicate detection.

### 2. Duplicate Detection System (`games.py`)
Added `_scan_and_fix_duplicates()` method that:

#### Hash Generation
- Checks each cover art for missing `image_hash` field
- Attempts to download the image and generate MD5 hash from actual image data
- Falls back to URL-based hash if download fails
- Updates the database with generated hashes

#### Duplicate Detection
- Tracks all seen hashes in a dictionary
- Identifies duplicates by comparing hashes
- Marks duplicate entries for removal
- Keeps the first occurrence of each unique image

#### Database Cleanup
- Removes duplicate entries from `cover_collection`
- Updates the database with cleaned collection
- Provides user feedback on actions taken

### 3. Enhanced `.draw covers` Command
The command now automatically:
1. Runs duplicate scan and cleanup before displaying collection
2. Shows notification of any fixes made:
   - "✅ Generated hashes for X image(s)"
   - "🗑️ Removed X duplicate(s)"
3. Displays the cleaned collection

## Usage

```bash
# View covers for a character (automatically scans and fixes)
.draw covers <UID>
.draw covers F9D6E292
.draw covers anya forger
```

## Technical Details

### Hash Generation Strategy
1. **Primary**: Download image and compute MD5 hash of actual image data
2. **Fallback**: Compute MD5 hash of image URL if download fails
3. **API Sources**: Use MD5 hash provided by booru APIs when available

### Duplicate Detection Logic
```python
seen_hashes = {}
for art in cover_arts:
    if art.hash in seen_hashes:
        # Duplicate! Mark for removal
        duplicates_to_remove.append(art.id)
    else:
        # First occurrence, keep it
        seen_hashes[art.hash] = art.id
```

### Database Structure
Cover arts are stored with the following fields:
- `id`: Unique identifier
- `image_url`: Full image URL
- `image_hash`: MD5 hash for duplicate detection
- `custom_name`: User-defined name
- `cost`: Purchase cost
- `unlocked_at`: Timestamp

## Benefits

1. **Automatic Cleanup**: Users don't need to manually identify duplicates
2. **Storage Efficiency**: Removes redundant data from database
3. **Better UX**: Cleaner collections without duplicate entries
4. **Future-Proof**: All new purchases include hashes automatically
5. **Backward Compatible**: Generates hashes for existing images on-demand

## Logging

The system logs all actions:
- `[Duplicate Scan] Generated hash for art {id}: {hash}`
- `[Duplicate Scan] Found duplicate: {id} is a copy of {original_id}`
- `[Duplicate Scan] Fixed inventory for {uid}: {hashes} hashes, {duplicates} duplicates`

## Error Handling

- Gracefully handles failed image downloads
- Falls back to URL-based hashing
- Continues processing even if individual images fail
- Logs all errors for debugging
