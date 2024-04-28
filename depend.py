import os
import subprocess

def update_requirements(requirements_file='requirements.txt'):
    # Get installed packages using pip
    installed_packages = subprocess.check_output(['pip', 'freeze']).decode('utf-8').split('\n')

    # Remove any empty strings or non-package lines
    installed_packages = [pkg for pkg in installed_packages if pkg.strip() and '==' in pkg]

    # Write installed packages to requirements file
    with open(requirements_file, 'w') as f:
        f.write('\n'.join(installed_packages))

    print(f"Updated {requirements_file} with installed packages.")

# Check if requirements.txt file exists, create if not
if not os.path.exists('requirements.txt'):
    open('requirements.txt', 'a').close()
    print("Created requirements.txt file.")

# Update requirements.txt with installed packages
update_requirements()
