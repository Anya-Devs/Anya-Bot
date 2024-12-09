# Use the official Python image from Docker Hub
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy all your project files into the container
COPY . /app

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose the port your server will run on (you can modify the port based on your config)
EXPOSE 8080

# Set the entry point for the container
CMD ["python", "main.py"]  # Replace with your actual Python script filename
