class WriteHere:
    def __init__(self):
        self.readme_content = ""
        self.ratings = {}
        self.variables = {}

    def add_title(self, title: str):
        self.readme_content += f"# {title}\n\n"

    def add_description(self, description: str):
        self.readme_content += f"## Description\n{description}\n\n"

    def add_variable_section(self, var_name: str, var_value: str):
        self.readme_content += f"### {var_name}\n{{var: {var_name}}}: {var_value}\n\n"
        self.variables[var_name] = var_value

    def add_image(self, img_path: str, alt_text: str, size_aspect_ratio: str = "300x300"):
        self.readme_content += f"![{alt_text}]({img_path} = {size_aspect_ratio})\n\n"

    def add_button(self, button_name: str, url: str):
        self.readme_content += f"[{button_name}]({url})\n\n"

    def add_rating(self, section_name: str, rating: int):
        """ Add rating to the given section """
        self.ratings[section_name] = rating
        self.readme_content += f"### Rating for {section_name}\n{rating}/5\n\n"

    def translate_variables(self):
        """ Translate all variables in the readme_content using self.variables """
        for var, value in self.variables.items():
            self.readme_content = self.readme_content.replace(f"{{var: {var}}}", value)

    def save_readme(self, filename: str):
        self.translate_variables()
        with open(filename, "w") as file:
            file.write(self.readme_content)
        print(f"README generated and saved as {filename}")

# Example Usage
def generate_readme():
    readme = WriteHere()

    # Title and Description
    readme.add_title("Anya Bot Project")
    readme.add_description("This project is a fun, interactive bot that helps you catch Pokémon on Discord.")

    # Variables Section
    readme.add_variable_section("Version", "1.0.0")
    readme.add_variable_section("Author", "Senko")

    # Images (URL or local file)
    readme.add_image("https://example.com/image.png", "Anya Bot Logo", "200x200")
    readme.add_image("assets/anya_bot_image.png", "Anya Bot in action", "300x300")

    # Buttons (Links)
    readme.add_button("Join the Discord", "https://discord.gg/example")
    readme.add_button("GitHub Repository", "https://github.com/example/repository")

    # Ratings for sections
    readme.add_rating("Project", 5)
    readme.add_rating("Description", 4)
    readme.add_rating("User Interface", 3)

    # Save the file
    readme.save_readme("README.md")

if __name__ == "__main__":
    generate_readme()
