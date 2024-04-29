import os
import asyncio
os.system("pip install -r requirements.txt")
os.system("pip install --upgrade pip")

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()