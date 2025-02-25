import subprocess
import os

def generate_requirements_txt():
    installed_packages = subprocess.check_output(['pip', 'freeze'])
    with open('requirements.txt', 'wb') as f:
        f.write(installed_packages)
    print("requirements.txt generated successfully.")

def check_opencv():
    try:
        import cv2
    except ImportError:
        print("OpenCV (cv2) not found. Installing...")
        subprocess.check_call(['pip', 'install', 'opencv-python-headless'])
        print("OpenCV (cv2) installed.")

def update_pip():
    subprocess.check_call(['pip', 'install', '--upgrade', 'pip'])
    print("pip updated successfully.")

def install_requirements():
    subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
    print("All requirements installed.")

if __name__ == '__main__':
    check_opencv()         
    generate_requirements_txt() 
    update_pip()     
    install_requirements()    
