# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Expose Streamlit's default port
EXPOSE 8080

# Run Streamlit app

CMD ["streamlit", "run", "dashboard.py", "--server.port=8080", "--server.enableCORS=false"]
