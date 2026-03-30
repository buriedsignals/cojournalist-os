# coJournalist

AI-powered local news monitoring platform.

## Overview

coJournalist lets users create "scouts" that monitor:
- **Web pages** for content changes
- **Local news** for daily digests
- **Search queries** for specific topics
- **Social media profiles** for new posts and deletions
- **Data APIs** for threshold alerts

Scouts run on schedules and send email notifications when criteria are met.

## Tech Stack

- **Frontend**: SvelteKit + TailwindCSS
- **Backend**: FastAPI (Python)
- **Infrastructure**: AWS Lambda + EventBridge + DynamoDB
- **Auth**: MuckRock OAuth 2.0
- **AI**: OpenRouter (configurable LLM)
- **Hosting**: Render (Docker)

## Quick Start

### Prerequisites
- Node.js 22 LTS
- Python 3.11+
- AWS CLI configured

### Local Development

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Environment Variables

Copy `.env.example` to `.env` and fill in the values.

## Deployment

The app deploys to Render via Docker. Push to `main` triggers automatic deployment.

```bash
git push origin main
```

## Documentation

- [AWS Architecture](docs/architecture/aws-architecture.md)
- [API Endpoints](docs/architecture/fastapi-endpoints.md)
- [AWS Deployment](aws/README.md)

## Project Structure

```
├── frontend/     # SvelteKit SPA
├── backend/      # FastAPI backend
├── aws/          # Lambda functions
├── docs/         # Architecture docs
└── Dockerfile    # Production build
```
