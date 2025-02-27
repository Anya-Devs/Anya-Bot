import os
os.system("pip install pipreqs")
import subprocess


def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', package], check=True)


def generate_requirements():
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv', '.'], check=True)


def start():
    generate_requirements()
    install_package('pipreqs')
    subprocess.run(['pip', 'install', '--upgrade', '-r', 'requirements.txt', 'pip'], check=True)

