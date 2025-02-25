"""
------------ SetUp Section ------------
> Scans all Python files in the project, generates a requirements.txt file 
  containing only necessary dependencies, and installs them.
"""

import subprocess

def install_package(package):
    """Ensures the given package is installed before running commands."""
    subprocess.run(['pip', 'install', '--quiet', package], check=True)

def generate_requirements():
    """Generates requirements.txt based on actual project imports."""
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)

# Ensure pipreqs is installed
install_package('pipreqs')

# Generate and install only necessary dependencies
generate_requirements()
subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)
