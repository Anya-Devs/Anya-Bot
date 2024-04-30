import os
from dotenv import load_dotenv
import asyncio

def install_dependencies():
    """Install dependencies from requirements.txt"""
    os.system("pip install -r requirements.txt")

def upgrade_pip():
    """Upgrade pip"""
    os.system("pip install --upgrade pip")

def load_environment_variables():
    """Load environment variables from .env file"""
    load_dotenv()

def setup():
    install_dependencies()
    upgrade_pip()
    load_environment_variables()

# Call the setup function
setup()
