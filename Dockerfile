# Stage 1: build the Angular frontend
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx ng build --configuration production

# Stage 2: Python runtime serving API + static frontend
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=frontend /build/dist/frontend/browser ./static

ENV PORT=8000
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
