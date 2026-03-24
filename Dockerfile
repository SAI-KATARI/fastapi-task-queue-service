FROM python:3.11-slim

WORKDIR /app

# copy requirements first so docker can cache this layer
# avoids reinstalling everything on every code change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# default command runs the API server
# worker containers override this in docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
