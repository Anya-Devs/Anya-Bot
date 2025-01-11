import os
import subprocess
import sys


class PackageInstaller:
    def __init__(self):
        # Define packages to install
        self.packages = [
            "discord.py",
            "colorama",
            "motor",
            "httpx",
            "colorlog",
            "opencv-python-headless",
            "pillow",
            "vaderSentiment",
            "python-Levenshtein",
            "scikit-image",
            "fuzzywuzzy",
            "openai",
            "psutil",
            "GitPython",
            "scikit-learn",
            "matplotlib",
            "seaborn",
            "imagehash",
            "scipy",
            "tqdm",
            "graphviz",
            "aiofiles",
        ]

    def install_packages(self):
        print("Running install_packages :D")
        # Construct the pip install command
        command = " && ".join([f"pip install {pkg}" for pkg in self.packages])

        # Run installations in single cmd
        os.system(command)


def upgrade_pip():
    """Upgrade pip to the latest version"""
    print("Upgrading pip...")
    os.system("pip install --upgrade pip")


def load_environment_variables():
    """Load environment variables from .env file"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv not found. Installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "python-dotenv"])
        # Reload sys.path after installation
        site_packages_path = next(p for p in sys.path if "site-packages" in p)
        if site_packages_path not in sys.path:
            sys.path.append(site_packages_path)
        from dotenv import load_dotenv

    # Load .env file
    load_dotenv()
    print("Loading environment variables from .env...")


if __name__ == "__main__":
    upgrade_pip()  # Update pip
    installer = PackageInstaller()
    installer.install_packages()  # Install requirements
    load_environment_variables()  # Set Envierment : Load
