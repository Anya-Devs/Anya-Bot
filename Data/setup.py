import os
import subprocess

# Function to install a package
def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', package], check=True)

# Function to generate requirements.txt
def generate_requirements():
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)

# Main function to generate and install necessary dependencies
def start():
    generate_requirements()
    install_package('pipreqs')
    subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)

