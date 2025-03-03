import os
os.system("pip install pipreqs")
import subprocess
import sys


def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', package], check=True)


def generate_requirements():
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)


def start():
    # Install opencv-python-headless
    install_package('opencv-python-headless')

    # Generate or update the requirements.txt file
    generate_requirements()

    # Install pipreqs if not already installed
    install_package('pipreqs')

    # Upgrade pip and install packages from requirements.txt
    subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)


if __name__ == "__main__":
    start()
