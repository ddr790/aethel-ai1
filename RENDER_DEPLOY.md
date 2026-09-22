# Aethel V22 — Render Ready

This package is prepared for deployment as a Render Web Service using Docker.

## Render settings
- Service type: Web Service
- Runtime: Docker
- Dockerfile: ./Dockerfile
- Health Check Path: /health
- The application reads Render's PORT environment variable and binds to 0.0.0.0.

## Important
The image generator has a local raster fallback, so it does not require an external image API. This fallback creates valid PNGs but is not a diffusion model. A real local diffusion model would require a separate GPU-capable service.

## Data
SQLite is included for the prototype. Render's normal service filesystem is ephemeral; for production persistence, use a persistent disk or migrate the database to a managed database.
