import os
import subprocess

submodule_url = "https://github.com/cringe-neko-girl/Poketwo-AutoNamer.git"
submodule_path = "submodules/poketwo_spawns"

def install_package(package):
    subprocess.run(['pip', 'install', '--quiet', '--upgrade', package], check=True)

def update_all_packages():
    outdated_packages = subprocess.run(
        ['pip', 'list', '--outdated', '--format=freeze'],
        capture_output=True, text=True
    ).stdout

    for package in outdated_packages.splitlines():
        package_name = package.split('==')[0]
        install_package(package_name)

    subprocess.run(['pip', 'check'], capture_output=True, text=True)

def clean_requirements():
    subprocess.run(['pipreqs', '--force', '--ignore', 'venv,.venv,submodules', '.'], check=True)

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

def sync_submodule():
    def run(*args):
        subprocess.run(args, check=True)

    if not os.path.exists(os.path.join(submodule_path, '.git')):
        print(f"Fixing submodule: {submodule_path}")
        
        try:
            run("git", "submodule", "add", submodule_url, submodule_path)
        except subprocess.CalledProcessError as e:
            print(f"Error while adding submodule: {e}")
            run("git", "submodule", "update", "--force", "--init", "--recursive")

    print("Cleaning submodule changes...")
    run("git", "submodule", "foreach", "--recursive", "git reset --hard")
    run("git", "submodule", "foreach", "--recursive", "git clean -fd")
    run("git", "submodule", "sync", "--recursive")
    run("git", "submodule", "update", "--init", "--remote", "--recursive")

def start():
    os.system("pip install --upgrade pip")

    install_package('pipreqs')
    install_package('onnxruntime')
    install_package('opencv-python-headless')
    install_package('python-Levenshtein')

    sync_submodule()
    update_all_packages()
    clean_requirements()

    subprocess.run(['pip', 'install', '--upgrade', '--no-cache-dir', '-r', 'requirements.txt'], check=True)

if __name__ == "__main__":
    start()
