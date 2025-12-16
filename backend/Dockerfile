FROM python:3.11-slim
WORKDIR /app

# Copy all source files
COPY . .

RUN pip install --upgrade pip && pip install -r requirements.txt

# Ensure wait-for-it.sh is executable (even if it is already, this guarantees it inside the container)
RUN chmod +x wait-for-it.sh

# Use wait-for-it.sh to wait for the database before starting the app
CMD ["./wait-for-it.sh", "db:5432", "--", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]