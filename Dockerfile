FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Install necessary dependencies for Chrome and chromedriver, including xvfb and xauth
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libgbm1 \
    libgtk-3-0 \
    libu2f-udev \
    xdg-utils \
    jq \
    xvfb \
    libxss1 \
    libappindicator1 \
    libindicator7 \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome stable
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Get latest stable chromedriver
RUN bash -c ' \
    CHROMEDRIVER_URL=$(curl -sS "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | jq -r ".channels.Stable.downloads.chromedriver[] | select(.platform==\"linux64\").url") && \
    wget -q "${CHROMEDRIVER_URL}" -O chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip && \
    rm -rf chromedriver-linux64 \
'

# Add Chrome to PATH
ENV PATH="/usr/bin/google-chrome-stable:$PATH"

COPY . .

# Command to run the Flask application using xvfb-run
# CMD ["sh", "-c", "xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' python hotstar.py"]
CMD ["sh", "-c", "export DISPLAY=:99 && xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' python hotstar.py"]