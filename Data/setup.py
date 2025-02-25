import subprocess
import os

# Generate requirements.txt based on installed packages
def generate_requirements_txt():
    installed_packages = subprocess.check_output(['pip', 'freeze'])
    with open('requirements.txt', 'wb') as f:
        f.write(installed_packages)
    print("requirements.txt generated successfully.")

# Ensure OpenCV (cv2) is installed if missing
def check_opencv():
    try:
        import cv2
    except ImportError:
        print("OpenCV (cv2) not found. Installing...")
        subprocess.check_call(['pip', 'install', 'opencv-python-headless'])
        print("OpenCV (cv2) installed.")

# Update pip to the latest version
def update_pip():
    subprocess.check_call(['pip', 'install', '--upgrade', 'pip'])
    print("pip updated successfully.")

# Install dependencies from requirements.txt
def install_requirements():
    subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
    print("All requirements installed.")

# Main execution flow
if __name__ == '__main__':
    check_opencv()            # Ensure OpenCV is installed
    generate_requirements_txt()  # Create requirements.txt
    update_pip()              # Update pip
    install_requirements()    # Install all dependencies
