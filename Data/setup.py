"""
------------ SetUp Section ------------
> Creates the requirements.txt file and downloads the latest versions first, then installs them.
"""
import os
import subprocess

def generate_requirements():
    with open('requirements.txt', 'w') as f:
        # Run the pip freeze command and capture the output
        result = subprocess.run(['pip', 'freeze'], stdout=subprocess.PIPE, text=True)
        # Write the output to the requirements.txt file
        f.write(result.stdout)

# Call the function to generate the requirements.txt file
generate_requirements()
os.system("pip install -r requirements.txt")

