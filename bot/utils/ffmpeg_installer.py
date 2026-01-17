"""
FFmpeg Auto-Installer
Downloads and installs FFmpeg automatically if not present.
Optimized for low resource usage with progress tracking.
"""

import zipfile
import urllib.request
from pathlib import Path
import time
from imports.log_imports import logger

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def install_ffmpeg():
    """Download and install ffmpeg if not present - optimized for low resource usage"""
    ffmpeg_dir = Path(__file__).parent.parent / "ffmpeg" / "ffmpeg-8.0.1-essentials_build"
    ffmpeg_exe = ffmpeg_dir / "bin" / "ffmpeg.exe"
    
    if ffmpeg_exe.exists():
        logger.info("✅ FFmpeg already installed")
        return
    
    logger.info("📦 FFmpeg not found. Starting installation...")
    
    # FFmpeg download URL (Windows essentials build)
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = Path(__file__).parent.parent / "ffmpeg_temp.zip"
    
    try:
        # Download with tqdm progress bar
        logger.info(f"⬇️  Downloading FFmpeg from {url}")
        
        if tqdm:
            # Use tqdm for better progress display
            response = urllib.request.urlopen(url)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192  # 8KB chunks for low memory usage
            
            with open(zip_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading", ncols=80) as pbar:
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        pbar.update(len(chunk))
                        time.sleep(0.001)  # Small delay to reduce CPU/network stress
        else:
            # Fallback without tqdm
            def progress_hook(block_num, block_size, total_size):
                if block_num % 100 == 0:  # Update less frequently
                    downloaded = block_num * block_size
                    percent = min(100, (downloaded / total_size) * 100)
                    logger.info(f"⬇️  Downloading: {percent:.1f}%")
            
            urllib.request.urlretrieve(url, zip_path, progress_hook)
        
        logger.info("✅ Download complete!")
        
        # Extract with progress - memory efficient
        logger.info("📂 Extracting FFmpeg (this may take a moment)...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            
            if tqdm:
                # Extract with tqdm progress
                for member in tqdm(members, desc="Extracting", ncols=80):
                    zip_ref.extract(member, Path(__file__).parent.parent / "ffmpeg")
                    time.sleep(0.0001)  # Tiny delay to reduce I/O stress
            else:
                # Extract without tqdm, log every 10%
                total = len(members)
                for i, member in enumerate(members):
                    zip_ref.extract(member, Path(__file__).parent.parent / "ffmpeg")
                    if i % max(1, total // 10) == 0:
                        percent = ((i + 1) / total) * 100
                        logger.info(f"📦 Extracting: {percent:.0f}%")
        
        logger.info("✅ FFmpeg extracted successfully!")
        
        # Rename extracted folder to expected name
        extracted_folders = list((Path(__file__).parent.parent / "ffmpeg").glob("ffmpeg-*"))
        if extracted_folders and not ffmpeg_dir.exists():
            extracted_folders[0].rename(ffmpeg_dir)
            logger.info(f"✅ FFmpeg configured at: {ffmpeg_dir}")
        
        # Cleanup
        if zip_path.exists():
            zip_path.unlink()
            logger.info("🧹 Cleaned up temporary files")
        
        logger.info("✅ FFmpeg installation complete!")
        
    except Exception as e:
        logger.error(f"❌ Error installing FFmpeg: {e}", exc_info=False)
        logger.warning("Please download manually from: https://ffmpeg.org/download.html")
        if zip_path.exists():
            try:
                zip_path.unlink()
            except:
                pass
