FROM ubuntu:22.04

# Set environment to suppress interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and ODBC prerequisites
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    software-properties-common \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip

# Optional: Set Python3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Add Microsoft SQL Server ODBC Driver repo and install
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg && \
    curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose the port for Uvicorn
EXPOSE 8000

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
