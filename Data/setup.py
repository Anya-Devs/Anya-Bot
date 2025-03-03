import os
import subprocess
import sys
import logging

os.system("pip install pipreqs")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_package_installed(package):
    try:
        subprocess.run(['pip', 'show', package], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def install_package(package):
    if not is_package_installed(package):
        try:
            logger.info(f"Installing {package}...")
            subprocess.run(['pip', 'install', '--quiet', package], check=True)
            logger.info(f"{package} installed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install {package}. Error: {e}")
            sys.exit(1)
    else:
        logger.info(f"{package} is already installed.")

def generate_requirements():
    try:
        if not os.path.exists('requirements.txt') or os.path.getsize('requirements.txt') == 0:
            logger.info("Generating requirements.txt...")
            subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)
            logger.info("requirements.txt generated successfully.")
        else:
            logger.info("requirements.txt already exists. Skipping generation.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate requirements.txt. Error: {e}")
        sys.exit(1)

def clean_requirements():
    try:
        with open('requirements.txt', 'r') as f:
            required_packages = f.readlines()

        installed_packages = subprocess.check_output(['pip', 'freeze'], text=True).splitlines()

        # Get only the installed packages that are in the requirements.txt
        required_packages_set = set([pkg.split('==')[0].strip() for pkg in required_packages])
        installed_packages_set = set([pkg.split('==')[0].strip() for pkg in installed_packages])

        # Find the unused packages in the requirements.txt
        unused_packages = required_packages_set - installed_packages_set

        # Rewrite the requirements.txt file without unused packages
        with open('requirements.txt', 'w') as f:
            for pkg in required_packages:
                if pkg.split('==')[0].strip() not in unused_packages:
                    f.write(pkg)

        logger.info("Removed unused packages from requirements.txt.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clean requirements.txt. Error: {e}")
        sys.exit(1)

def start():
    install_package('pipreqs')
    generate_requirements()
    clean_requirements()
    try:
        logger.info("Upgrading pip and installing packages from requirements.txt...")
        subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)
        logger.info("Pip upgraded and requirements installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install requirements. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start()
