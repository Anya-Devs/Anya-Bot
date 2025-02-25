import os
import subprocess
import ast

def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', package], check=True)

def generate_requirements():
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)


# Generate and install only necessary dependencies
def start():
 generate_requirements()
 install_package('pipreqs')
 subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)
