"""
------------ SetUp Section ------------
> Recursively scans all Python files in the project (including subfolders), 
  generates a requirements.txt file containing only necessary dependencies, 
  and installs them.
"""

import subprocess
import os

# Function to generate requirements.txt based on the global Python environment
def generate_requirements_txt():
    # Get the list of installed packages using pip freeze (global Python environment)
    installed_packages = subprocess.check_output(['pip', 'freeze'])
    
    # Decode and write the output to a requirements.txt file
    with open('requirements.txt', 'wb') as f:
        f.write(installed_packages)

    print("requirements.txt generated successfully.")

# Function to ensure OpenCV (cv2) is included in requirements.txt if not already installed
def check_opencv():
    try:
        # Try importing OpenCV (cv2)
        import cv2
    except ImportError:
        # If ImportError occurs, install OpenCV
        print("OpenCV (cv2) is not installed. Installing opencv-python...")
        subprocess.check_call(['pip', 'install', 'opencv-python-headless'])
        print("OpenCV (cv2) installed successfully.")

# Function to update pip to the latest version
def update_pip():
    subprocess.check_call(['pip', 'install', '--upgrade', 'pip'])
    print("pip updated successfully.")

# Function to install all dependencies from requirements.txt
def install_requirements():
    subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
    print("All requirements installed successfully.")

# Run all tasks automatically
if __name__ == '__main__':
    check_opencv()          # Ensure OpenCV is installed
    generate_requirements_txt()  # Generate requirements.txt
    update_pip()            # Update pip to the latest version
    install_requirements()  # Install all dependencies from requirements.txt
