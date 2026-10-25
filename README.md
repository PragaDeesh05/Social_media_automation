# IncuBrix Growth Engine
## AI-Powered Social Media Content & Autonomous Automation Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.x-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![MinIO](https://img.shields.io/badge/MinIO-S3_Compatible-C72C48?style=flat&logo=minio&logoColor=white)](https://min.io)
[![Redis](https://img.shields.io/badge/Redis-7.x-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-9.0+-007808?style=flat&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)

An enterprise-grade, full-stack social media automation engine engineered for the **IncuBrix Growth Engineer Assessment**. The system converts a single long-form input (blog, podcast, webinar, demo recording, transcript, PDF, or document) into a fully grounded, 30-day, multi-platform social media campaign across **Instagram**, **Facebook**, **YouTube**, and **X**.

---

## 1. Executive Summary & Capabilities

- **Zero-Mock Policy**: 100% genuine integrations. If an OAuth connection is unlinked, the publisher logs transparent diagnostics instead of fabricating fake successes.
- **Strict Evidence Grounding**: The engine extracts verified empirical facts, key claims with citation evidence, and verbatim quotes with source context. Hallucination of client names or fabricated statistics is strictly prevented.
- **Multi-Format Media Engine**:
  - **Text Posts**: Platform-adapted copy, hooks, hashtags, and CTAs (strictly enforcing the 280-character limit for X).
  - **Brand Graphics**: High-contrast, high-typography 1080x1080 cards rendered dynamically via Pillow and synced to MinIO S3 alongside an editable `source.json` config.
  - **5-Slide Carousels**: 1080x1350 vertical slides with progress bar, slide index, brand pill badges, and editable timeline.
  - **Short Videos & Reels**: Vertical 9:16 (1080x1920) broadcast videos ($\le$ 60 seconds) assembled via FFmpeg with native text-to-speech audio narration and synchronized burned-in subtitles.
- **Enterprise Publishing Pipeline**: PostgreSQL atomic row-level locks (`SELECT ... FOR UPDATE SKIP LOCKED`), idempotent keys, exponential backoff retries, and Fernet-encrypted OAuth token storage.

---

## 2. Architecture & Service Boundaries

```
                           +-------------------------------------------------------+
                           |               React 19 + Vite Dashboard               |
                           |  Midnight Rail UI • Calendar • Multi-Format Editor     |
                           +---------------------------+---------------------------+
                                                       |
                                            REST / Presigned URLs
                                                       |
                                                       v
                           +-------------------------------------------------------+
                           |              FastAPI Application Server               |
                           |       Correlation IDs • JWT Auth • OAuth Router       |
                           +----+----------------------+-----------------------+---+
                                |                      |                       |
            +-------------------+---+        +---------+-----------+      +----+------------------+
            | AI & Media Processing |        | Persistence & Queue |      | Platform Adapters     |
            +-----------------------+        +---------------------+      +-----------------------+
            | • ContentAnalyzer     |        | • PostgreSQL 16     |      | • Meta Graph v19      |
            | • CampaignPlanner     |        | • Redis 7 Queue     |      | • YouTube Data v3     |
            | • PostGenerator (UTM) |        | • MinIO S3 Storage  |      | • X API v2 (OAuth 2)  |
            | • ImageService        |        | • Atomic Locks      |      | • Honest Diagnostics  |
            | • CarouselService     |        +---------------------+      +-----------------------+
            | • VideoService (TTS)  |
            +-----------------------+
```

### Directory Structure
```
Social_media_automation/
├── backend/
│   ├── alembic/                      # Database migrations
│   ├── app/
│   │   ├── api/v1/                   # REST Endpoints
│   │   │   └── routes/               # Health, Auth, Brand, Sources, Campaigns, Assets, Calendar, Publishing, Media, Analytics
│   │   ├── core/                     # Config, Logging, Security (Fernet/Bcrypt), Exceptions
│   │   ├── db/
│   │   │   ├── models/               # 18 Normalized SQLAlchemy 2.x Models
│   │   │   └── session.py            # Async engine & sessionmaker (NullPool)
│   │   ├── integrations/             # Meta, YouTube, X, MinIO adapters
│   │   ├── schemas/                  # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── ai/                   # Gemini model adapter, semantic analyzer, 30-day matrix planner
│   │   │   ├── content/              # Post copy generator, deterministic UTM tracking
│   │   │   ├── images/               # 1080x1080 Brand cards & 1080x1350 Carousels
│   │   │   ├── video/                # Windows TTS synthesis & FFmpeg 9:16 short video assembly
│   │   │   ├── validation/           # Brand, platform constraint, and duplicate checkers
│   │   │   ├── publishing/           # Idempotent publisher & platform registry
│   │   │   ├── storage/              # MinIO S3 object client & presigned URLs
│   │   │   └── analytics/            # Verified metrics aggregation
│   │   ├── workers/                  # Background worker loop with atomic row-level locking
│   │   └── main.py                   # FastAPI lifespan application
│   ├── tests/                        # 14 unit tests & end-to-end integration test
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── components/               # Badges (Platform, Format, Status) & Midnight Rail Layout
    │   ├── features/
    │   │   ├── dashboard/            # KPI summaries, upcoming slots, connection health
    │   │   ├── campaigns/            # 4-step wizard campaign creation
    │   │   ├── uploads/              # Source analysis & evidence citation inspection
    │   │   ├── content-calendar/     # 30-day interactive calendar (Day/Week/Month)
    │   │   ├── asset-editor/         # Dedicated text, image, carousel, & video editors
    │   │   ├── connected-accounts/   # OAuth connection hub with scope audits
    │   │   ├── publishing/           # Queue table with retry & manual publish controls
    │   │   ├── media-library/        # MinIO authenticated asset browser
    │   │   ├── analytics/            # Verified performance metrics & Launch Kit exporter
    │   │   └── settings/             # Brand governance, prohibited terms, design palette
    │   ├── services/                 # Central Axios API client with auto-auth interceptor
    │   └── types/                    # Full TypeScript contract matching backend schemas
    └── package.json
```

---

## 3. Technology Stack & Service Configuration

| Layer | Service / Library | Version / Port | Purpose |
|---|---|---|---|
| **Backend** | Python / FastAPI | 3.13 / `8005` (`0.0.0.0`) | REST API, async route handling, middleware |
| **Database** | PostgreSQL 16 | `5434` (`incubrix_social`) | 18 normalized tables, relational integrity, row locks |
| **Object Store** | MinIO (S3-compatible) | `9100` (`incubrix-assets`) | Media storage (PNG, MP4, SRT, source.json) |
| **Caching/Jobs** | Redis | `6379` | Task coordination & worker state |
| **Media Engine** | FFmpeg & FFprobe | 9.0.2 / Native | Video scaling (1080x1920), audio muxing, subtitle burn |
| **Speech (TTS)** | Windows Native Speech | `System.Speech` | Offline, zero-latency human narration synthesis |
| **AI Models** | Google Gemini SDK | `gemini-flash-lite-latest` | Chunked semantic analysis, 30-day matrix, post copy |
| **Frontend** | React 19 + TypeScript | `5174` (`0.0.0.0`) | Midnight Rail dashboard, interactive canvas |
| **CSS Styling** | Tailwind CSS 3.4 | — | Custom dark theme, typography, crisp scrollbars |

---

## 4. Local Setup & Installation

### Prerequisites
- Python 3.11+ (Python 3.13 tested and verified)
- Node.js 20+ (Node 22 tested and verified)
- PostgreSQL 16 running on port `5434`
- MinIO running on port `9100` (Access Key: `minioadmin`, Secret Key: `minioadmin`)
- Redis running on port `6379`
- FFmpeg installed and accessible in system `PATH`

### Step 1: Clone and Configure Environment
1. Clone the repository and navigate to the project directory:
   ```bash
   cd Social_media_automation
   ```
2. Verify or update backend configuration in `backend/.env`:
   ```env
   PROJECT_NAME="IncuBrix Social Media Automation Engine"
   DATABASE_URL=postgresql+asyncpg://incubrix:incubrix_dev@localhost:5434/incubrix_social
   REDIS_URL=redis://localhost:6379/0
   MINIO_ENDPOINT=localhost:9100
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin
   MINIO_BUCKET_NAME=incubrix-assets
   MINIO_SECURE=False
   GEMINI_API_KEY=your-gemini-api-key-here
   GEMINI_MODEL=gemini-flash-lite-latest
   GEMINI_FALLBACK_MODEL=gemini-3.8-flash
   FERNET_ENCRYPTION_KEY=your-32-byte-base64-fernet-key-here
   JWT_SECRET_KEY=change-this-to-a-strong-random-secret
   ```

### Step 2: Database Initialization & Seeding
1. Run database migrations with Alembic:
   ```bash
   cd backend
   venv\Scripts\python -m alembic upgrade head
   ```
2. Seed initial test examiner account and IncuBrix brand profile:
   ```bash
   venv\Scripts\python -m app.db.init_db
   ```
   **Default Seed Credentials**:
   - **Email**: `lead@incubrix.com`
   - **Password**: `IncuBrix2026!`

### Step 3: Run Backend & Background Worker
1. Start the FastAPI API server:
   ```bash
   cd backend
   venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
   ```
   *Interactive Swagger Documentation*: `http://localhost:8005/docs`
2. In a separate terminal, start the background worker:
   ```bash
   cd backend
   venv\Scripts\python -m app.workers.background_worker
   ```

### Step 4: Run Frontend Dashboard
1. Start the Vite React development server:
   ```bash
   cd frontend
   npm run dev
   ```
2. Open `http://localhost:5174` in your browser. The app will auto-authenticate using the seeded credentials.

---

## 5. Verification & Automated Testing

### Running the Test Suite
The test suite validates content safety, character limits, S3 storage presigning, token encryption roundtrips, and REST endpoints:
```bash
cd backend
venv\Scripts\python -m pytest backend/tests -k "not e2e"
```
**Expected Output**:
```
======================= 14 passed, 1 warning in 13.55s =======================
```

### Running the End-to-End Workflow Verification
Execute the complete end-to-end simulation from raw text to 30-day campaign planning, multi-format media generation, MinIO uploads, scheduling, and analytics:
```bash
cd backend
venv\Scripts\python backend/tests/e2e_workflow_test.py
```
**Verification Highlights**:
- ✅ Analyzes long-form input using Gemini and extracts verified claims and quotes.
- ✅ Plans 30-day campaign with 5 content pillars across Instagram, Facebook, YouTube, and X.
- ✅ Renders 1080x1080 brand graphic card and uploads PNG + `source.json` to MinIO.
- ✅ Renders 5-slide 1080x1350 carousel and uploads all 5 PNGs + `source.json` to MinIO.
- ✅ Assembles vertical 9:16 short video ($\le$ 60s) with TTS narration and synced subtitles.
- ✅ Enqueues scheduled posts in the publishing queue.
- ✅ Demonstrates honest error reporting when third-party OAuth access tokens are unlinked.
- ✅ Computes aggregate campaign analytics.

---

## 6. Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status (Postgres, MinIO, Redis) |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT bearer token |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile |
| `GET` | `/api/v1/brand-profiles` | List user brand guidelines |
| `POST` | `/api/v1/sources/upload` | Multipart file upload (PDF, DOCX, TXT, Audio, Video) |
| `POST` | `/api/v1/sources/text` | Direct text / URL ingestion |
| `GET` | `/api/v1/sources/{id}` | Inspect extraction, claims, and quotes |
| `POST` | `/api/v1/campaigns` | Generate 30-day campaign plan |
| `GET` | `/api/v1/assets` | Filter and query generated campaign assets |
| `PUT` | `/api/v1/assets/{id}` | Edit caption, hook, hashtags, and CTA |
| `POST` | `/api/v1/assets/{id}/regenerate-media` | Regenerate asset media without regenerating campaign |
| `GET` | `/api/v1/calendar` | 30-day schedule slots across platforms |
| `GET` | `/api/v1/publishing/queue` | View pending, scheduled, and published queue items |
| `POST` | `/api/v1/publishing/{id}/retry` | Manually retry a failed publishing attempt |
| `GET` | `/api/v1/media` | Browse all MinIO media assets with presigned URLs |
| `GET` | `/api/v1/analytics/campaign/{id}` | Retrieve real engagement and click analytics |

---

## 7. Compliance & Production Standards

1. **Security & Redaction**:
   - OAuth access and refresh tokens are encrypted at rest using AES-256 via Fernet symmetric encryption.
   - Credentials and client secrets are stripped from API responses.
2. **SSRF & URL Safe Ingestion**:
   - URL ingestion validates private IP ranges (`10.x.x.x`, `192.168.x.x`, `127.x.x.x`, `localhost`) to prevent Server-Side Request Forgery.
3. **Storage Governance**:
   - No media binaries are stored solely on the local filesystem. All files, subtitles, and editable source configs reside in MinIO with short-lived presigned URLs.
4. **Idempotency & Concurrency**:
   - Background worker utilizes `SELECT ... FOR UPDATE SKIP LOCKED` to allow seamless multi-worker clustering without duplicate publishing.
