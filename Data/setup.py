import os
import subprocess


def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', '--upgrade', package], check=True)


def update_all_packages():
    """Upgrades all installed packages to their latest versions and removes duplicates."""
    outdated_packages = subprocess.run(
        ['pip', 'list', '--outdated', '--format=freeze'],
        capture_output=True, text=True
    ).stdout

    for package in outdated_packages.splitlines():
        package_name = package.split('==')[0]
        install_package(package_name)

    subprocess.run(['pip', 'check'], capture_output=True, text=True)


def clean_requirements():
    """Regenerates requirements.txt with the latest versions and removes duplicates."""
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.', 'detectron2'], check=True)

    with open('requirements.txt', 'r') as file:
        lines = file.readlines()

    unique_packages = {}
    for line in lines:
        if '==' in line:
            package, version = line.strip().split('==')
            unique_packages[package] = version 

    with open('requirements.txt', 'w') as file:
        for package, version in unique_packages.items():
            file.write(f"{package}=={version}\n")


def start():
    
    os.system("pip install --upgrade pip")
    #os.system("pip install git+https://github.com/facebookresearch/detectron2.git --no-build-isolation")
    
    install_package('pipreqs')
    install_package('opencv-python-headless')
    install_package('python-Levenshtein')

    
    update_all_packages()
    clean_requirements()

   

    
    subprocess.run(['pip', 'install', '--upgrade', '--no-cache-dir', '-r', 'requirements.txt'], check=True)


if __name__ == "__main__":
    start()
