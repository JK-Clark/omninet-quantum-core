FROM python:3.11

# Install FastAPI and other dependencies
RUN pip install fastapi uvicorn

# Set working directory
WORKDIR /app

COPY . /app

# Command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
