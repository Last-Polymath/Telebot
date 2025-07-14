# Step 1: Choose a base image. We'll use a slim Python image to keep it lightweight.
# 'bullseye' is a stable version of the Debian OS.
FROM python:3.10-slim-bullseye

# Step 2: Install system dependencies.
# Your bot requires FFmpeg to merge the best quality video and audio streams.
# We update the package list, install ffmpeg, and then clean up to keep the image small.
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Step 3: Set the working directory inside the container.
# This is where our bot's files will be stored and run from.
WORKDIR /app

# Step 4: Copy the requirements file into the container.
# We copy this first to take advantage of Docker's layer caching.
# The dependencies layer will only be rebuilt if this file changes.
COPY requirements.txt .

# Step 5: Install the Python dependencies from the requirements file.
# --no-cache-dir ensures we don't store the download cache, making the final image smaller.
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Copy the rest of your bot's code into the container.
# The '.' means copy everything from the current directory (on your computer)
# into the working directory inside the container ('/app').
COPY . .

# Step 7: Specify the command to run when the container starts.
# Replace 'your_bot_script.py' with the actual filename of your Python bot script.
CMD ["python", "bot.py"]
