"""
Game utilities module for Anya Bot - Image generation and game logic.
"""
from .const import *
from .fonts import _load_emoji_font
from .images import *
from .view import *

# automatically build the public API list from imported modules
def _build_public_api():
    public_api = ['_load_emoji_font']
    from . import images
    public_api.extend([name for name in dir(images) if name.startswith('generate_')])
    public_api.extend(['fetch_avatar_bytes'])
    from . import const
    config_vars = [
        name for name in dir(const) 
        if not name.startswith('_') and 
           name.isupper() and 
           not callable(getattr(const, name, None))
    ]
    public_api.extend(config_vars)
    
    # Add view classes if available
    try:
        from . import view
        view_classes = [name for name in dir(view) if name.endswith('View') and not name.startswith('_')]
        public_api.extend(view_classes)
    except ImportError:
        pass
    
    return public_api

__all__ = _build_public_api()
