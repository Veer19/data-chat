#!/bin/bash
apt-get update && \
    apt-get install -y curl gnupg unixodbc-dev gcc g++ && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18
python -m uvicorn main:app --host 0.0.0.0
