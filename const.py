# const.py

class LogConstants:
    """
    Constants related to logging.
    """
    # URL of the thumbnail image for the start log embed
    start_log_thumbnail = "https://example.com/start_log_thumbnail.png"
    
    # Footer details
    footer_text = "Please commit your changes to the repository."
    footer_icon = "https://example.com/footer_icon.png"
    
    # Author details
    author_name = "Your Bot Name"
    author_icon = "https://example.com/author_icon.png"


class PingConstants:
    """
    Constants related to the ping command.
    """
    # Thumbnail URL for the ping command
    thumbnail_url = "https://example.com/ping_thumbnail.png"
    
    # Embed color
    embed_color = 0x00ff00
    
    # System information
    system_info = {
        "Operating System": f"{platform.system()} {platform.release()} ({platform.version()})",
        "Processor": platform.processor(),
        "Python Version": platform.python_version()
    }
    
    # Language information
    language_info = {
        "Language": "Python",
        "Discord Library": f"discord.py {discord.__version__}"
    }
