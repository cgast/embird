# EmBird Mobile App Feasibility Report

## Executive Summary

**A fully on-device mobile app is not feasible.** The core processing pipeline — hourly web crawling, Cohere API embedding generation, FAISS clustering, and UMAP visualization — requires sustained background execution, a Python scientific computing stack, and server-side API key management that mobile platforms cannot support.

**The recommended approach is an offline-capable mobile app with a minimal backend.** This split moves all heavy processing to a small server while the mobile app handles display, caching, and offline reading. This architecture also creates a natural billing boundary: the backend becomes the metered service.

---

## 1. Why Fully On-Device Is Not Feasible

### 1.1 Background Processing Restrictions

The crawler (`app/services/crawler.py`) runs in an infinite loop with a 1-hour sleep cycle, fetching potentially hundreds of URLs per cycle. The embedding worker (`app/services/embedding_worker.py`) similarly loops hourly to rebuild FAISS indices and regenerate visualizations.

| Platform | Background Limit | Impact |
|----------|-----------------|--------|
| **iOS** | ~30 seconds for background tasks; BackgroundTasks framework allows ~30 min but unreliable timing, no guaranteed scheduling | Cannot run hourly crawl cycles. iOS aggressively kills background processes. |
| **Android** | Doze mode suspends network after screen off; WorkManager allows periodic work but minimum interval is 15 min with no precision guarantee | Crawling would be inconsistent. Battery optimization kills long-running tasks. |

The crawler needs to: fetch RSS feeds, follow links, download full articles, extract content, call Cohere API for each article — this chain of network calls cannot complete within mobile background time limits.

### 1.2 Python Scientific Stack Has No Mobile Runtime

The core processing depends on libraries that have no mobile equivalents:

| Library | Purpose | Mobile Alternative? |
|---------|---------|-------------------|
| `faiss-cpu` (C++ via Python) | Vector similarity search | Partial — FAISS has iOS/Android builds but no Python bindings on mobile |
| `umap-learn` | Dimensionality reduction for visualization | **None** — requires numpy + scikit-learn + numba |
| `scikit-learn` | ML utilities, clustering support | **None** for mobile |
| `numpy` | Array operations throughout | Partial — ONNX Runtime, but not drop-in |
| `readability-lxml` / `newspaper3k` | Article content extraction | Would need JS/native reimplementation |
| `feedparser` | RSS parsing | Available in JS/native equivalents |
| `sqlalchemy` + `asyncpg` + `pgvector` | PostgreSQL ORM with vector support | **None** — no PostgreSQL on mobile |

Rewriting the FAISS clustering, UMAP projection, and content extraction pipeline in Swift/Kotlin would be a 3-6 month engineering effort and would still face the background processing limitations above.

### 1.3 API Key Security

The Cohere API key (`COHERE_API_KEY`) is used for every embedding generation — both during crawling and during user search queries. Embedding this key in a mobile app would expose it to extraction via decompilation. A server-side proxy is required regardless.

### 1.4 Database Requirements

The current system uses:
- **PostgreSQL + pgvector**: 1024-dimensional vector storage with IVFFlat indexing and cosine similarity search. No mobile equivalent.
- **SQLite**: Only for URL source management (trivial).

While the data volume is mobile-compatible (~66 MB for 10K articles), the vector operations require pgvector or FAISS, not standard SQLite.

---

## 2. Recommended Architecture: Offline-Capable App + Minimal Backend

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────┐
│              MINIMAL BACKEND                │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Crawler   │  │ Embedding│  │ PostgreSQL│ │
│  │ (hourly)  │  │ Worker   │  │ + pgvector│ │
│  └──────────┘  └──────────┘  └───────────┘ │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │        Sync API (REST/gRPC)          │   │
│  │  • GET /sync/news?since=<timestamp>  │   │
│  │  • GET /sync/clusters                │   │
│  │  • GET /sync/umap                    │   │
│  │  • POST /search (proxied Cohere)     │   │
│  │  • Auth + API key management         │   │
│  └──────────────────────────────────────┘   │
└──────────────────────┬──────────────────────┘
                       │ HTTPS
                       │ (periodic sync + search)
┌──────────────────────▼──────────────────────┐
│              MOBILE APP                      │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ SQLite   │  │ Sync     │  │ UI Layer  │ │
│  │ (cached  │  │ Manager  │  │ (all      │ │
│  │  news +  │  │ (delta   │  │  current  │ │
│  │  clusters│  │  updates) │  │  views)   │ │
│  │  + UMAP) │  └──────────┘  └───────────┘ │
│  └──────────┘                                │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Offline Capabilities                 │   │
│  │  • Read cached news                   │   │
│  │  • Browse cached clusters             │   │
│  │  • View cached UMAP visualization     │   │
│  │  • Local text search (FTS5)           │   │
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 2.2 What Stays on the Backend

These components **must** remain server-side:

| Component | Why It Can't Move | Current Location |
|-----------|------------------|-----------------|
| **Crawler loop** | Requires sustained background networking; hourly cycle | `app/services/crawler.py` |
| **Cohere embedding calls** | API key must stay server-side; called per article + per search | `app/services/embedding.py` |
| **FAISS index build + clustering** | Requires faiss-cpu, numpy, transitive clustering algorithm | `app/services/faiss_service.py` |
| **UMAP generation** | Requires umap-learn, scikit-learn, numpy | `app/services/visualization.py` |
| **Content extraction** | readability-lxml + newspaper3k; could theoretically move but tightly coupled to crawler | `app/services/extractor.py` |
| **PostgreSQL + pgvector** | Vector similarity search, IVFFlat index | `app/models/news.py` |

### 2.3 What Moves to the Mobile App

| Component | Mobile Implementation | Offline? |
|-----------|----------------------|----------|
| **News browsing** (Dashboard, NewsList, NewsDetail) | SQLite cache of synced articles | Yes |
| **Cluster viewing** (NewsClusters) | Cache pre-computed cluster JSON | Yes |
| **UMAP visualization** (UmapVisual) | Cache pre-computed UMAP coordinates; render with native 2D canvas | Yes |
| **Trending** | Local query on cached hit_count | Yes |
| **Text search** | SQLite FTS5 full-text search on title + summary | Yes |
| **Semantic search** | Requires backend call (Cohere embedding + FAISS) | No — needs network |
| **URL/source management** | Local SQLite + sync to backend | Partial |
| **Preference vectors** | Local storage + sync; embedding generation requires backend | Partial |

### 2.4 Sync Protocol Design

The sync mechanism is the critical piece. A delta-sync approach minimizes bandwidth:

**Sync endpoint: `GET /api/sync?since=<ISO-timestamp>`**

Returns:
```json
{
  "news": [
    { "id": 123, "title": "...", "summary": "...", "url": "...",
      "source_url": "...", "hit_count": 3, "first_seen_at": "...",
      "last_seen_at": "...", "deleted": false }
  ],
  "clusters": { ... },      // Full cluster JSON (small payload)
  "umap": [ ... ],           // Full UMAP coordinates (small payload)
  "deleted_ids": [45, 67],   // News items removed by retention policy
  "server_time": "..."       // For next sync's `since` parameter
}
```

**Sync frequency**: On app open + every 30-60 minutes while active. No background sync needed — data is not time-critical enough to justify push notifications for every article.

**Data size estimates per sync**:
- Full initial sync: ~66 MB (10K articles + cluster/UMAP JSON)
- Delta sync (1 hour): ~0.5-2 MB (50-200 new/updated articles)
- Cluster + UMAP refresh: ~2 MB

---

## 3. Data Volume Analysis

| Data Type | Per Item | Max Items | Total Size |
|-----------|----------|-----------|------------|
| News text (title + summary + URLs + metadata) | ~2.4 KB | 10,000 | ~24 MB |
| Embeddings (if synced for local similarity) | 4 KB (1024 × float32) | 10,000 | ~40 MB |
| Cluster JSON (pre-computed) | — | 1 | ~1 MB |
| UMAP coordinates JSON (pre-computed) | — | 1 | ~1 MB |
| **Total without embeddings** | | | **~26 MB** |
| **Total with embeddings** | | | **~66 MB** |

**Recommendation**: Do NOT sync embeddings to mobile. They are only needed for semantic search, which requires the Cohere API anyway. This cuts the sync payload from ~66 MB to ~26 MB for a full sync.

---

## 4. Mobile Technology Choices

### 4.1 Option A: Capacitor/Ionic Wrapper (Fastest Path)

Wrap the existing Vue 3 frontend (`frontend/src/`) in Capacitor.

| Pros | Cons |
|------|------|
| Reuse 100% of existing Vue 3 UI code | WebView performance for UMAP visualization may lag |
| Add SQLite plugin for offline cache | Not a truly "native" feel |
| Ship to iOS + Android from single codebase | Push notifications require native plugin |
| Minimal development effort | App Store review may question WebView-only apps |

**Estimated effort**: 2-3 weeks to add Capacitor, SQLite caching, and sync logic.

**Key changes to existing frontend**:
- Replace `fetch('/api/...')` calls with a sync-aware data layer that reads from local SQLite first
- Add a `SyncManager` service that handles delta syncs
- Add offline detection and stale-data indicators
- Capacitor plugins: `@capacitor/sqlite`, `@capacitor/network`, `@capacitor/preferences`

### 4.2 Option B: React Native / Expo

Rewrite the frontend in React Native.

| Pros | Cons |
|------|------|
| True native components, better UX | Full rewrite of 8 views + components |
| Better performance for UMAP canvas rendering | Need to learn/use React instead of Vue |
| Mature ecosystem for offline-first (WatermelonDB, etc.) | Higher development effort |
| Easier App Store approval | Two codebases to maintain |

**Estimated effort**: 6-8 weeks for feature parity.

### 4.3 Option C: Flutter

Rewrite in Flutter/Dart.

| Pros | Cons |
|------|------|
| Single codebase, true native performance | Full rewrite, new language (Dart) |
| Excellent offline/SQLite support | Smaller ecosystem than React Native |
| Canvas rendering for UMAP is fast | No code reuse from Vue frontend |

**Estimated effort**: 6-8 weeks for feature parity.

### 4.4 Recommendation

**Start with Option A (Capacitor)** for speed to market. The existing Vue 3 frontend is well-structured with clean component separation. The UMAP visualization (which uses D3) will work in a WebView. If performance or native feel becomes an issue, migrate to React Native later.

---

## 5. Backend Simplification for Billing

The current Docker Compose setup runs 4 containers (webapp, crawler, embeddings, postgres). For a per-user or per-group SaaS model, this can be simplified:

### 5.1 Minimal Backend Architecture

```
Single Container (or two):
├── FastAPI app (serves sync API + proxies search)
├── Crawler (background asyncio task in same process)
├── Embedding worker (background asyncio task in same process)
└── PostgreSQL (separate managed service, e.g., Supabase, Neon)
```

The current code already supports running crawler and embedding tasks in the same process — `SERVICE_TYPE` in `entrypoint.sh` just controls which loop to start. Merging them into a single process with multiple asyncio tasks is straightforward.

### 5.2 Billing-Friendly Changes

| Change | Why |
|--------|-----|
| **Add user authentication** (currently none) | Required for per-user billing and data isolation |
| **Add per-user URL source limits** | Bound crawling costs (e.g., free: 5 sources, paid: 50) |
| **Add per-user Cohere API usage tracking** | Embedding calls are the primary variable cost (~$0.10/1M tokens) |
| **Consolidate into single process** | Reduce hosting cost per user; one container instead of four |
| **Use managed PostgreSQL** | Avoid running Postgres in a container per user (use Supabase/Neon with row-level security) |
| **Add API rate limiting** | Prevent abuse, enforce tier limits |

### 5.3 Cost Model

Per-user backend costs (estimated):

| Resource | Cost Estimate |
|----------|--------------|
| Cohere embeddings (1K articles/month) | ~$0.02/month |
| Managed PostgreSQL (shared, ~50 MB/user) | ~$0.50/month (at scale with Neon/Supabase) |
| Compute (shared container, light crawling) | ~$1-3/month |
| **Total per-user backend cost** | **~$2-4/month** |

This supports a pricing model of $5-10/month per user with healthy margins.

---

## 6. Implementation Roadmap

### Phase 1: Backend API Preparation (1-2 weeks)
1. Add authentication (JWT or API keys per user)
2. Create sync endpoint (`GET /api/sync?since=<timestamp>`)
3. Add `deleted_at` soft-delete column to news table for sync
4. Consolidate services into single process
5. Add per-user data isolation (user_id foreign key or tenant schema)

### Phase 2: Mobile App Shell (1-2 weeks)
1. Add Capacitor to existing Vue 3 project
2. Set up SQLite local database with schema matching backend
3. Implement SyncManager service
4. Add offline detection + stale data indicators
5. Replace direct API calls with cache-first data layer

### Phase 3: Offline Features (1-2 weeks)
1. Implement local SQLite FTS5 for text search
2. Cache cluster JSON for offline cluster browsing
3. Cache UMAP coordinates for offline visualization
4. Add "last synced" indicator in UI
5. Handle sync conflicts (server wins strategy)

### Phase 4: Search + Polish (1 week)
1. Semantic search → calls backend when online, falls back to FTS5 offline
2. Push notification support for breaking news clusters (optional)
3. App Store preparation (icons, screenshots, metadata)
4. Performance optimization and testing

### Phase 5: Billing Integration (1-2 weeks)
1. Integrate Stripe/RevenueCat for subscriptions
2. Add usage tracking dashboard
3. Implement tier limits (sources, search queries)
4. Add onboarding flow

---

## 7. Key Technical Decisions

### 7.1 Do NOT Sync Embeddings
The 1024-dimensional float32 vectors add ~40 MB to the sync payload and have no use on the mobile device. Semantic search requires the Cohere API regardless (to embed the query), so it always needs the backend. Local search uses SQLite FTS5 on text fields.

### 7.2 Pre-Compute Everything Possible
The current architecture already pre-computes clusters and UMAP. For mobile, also pre-compute:
- Trending news rankings
- Per-preference-vector relevance scores for each article
- Cluster keyword names

This minimizes the mobile app's computational requirements to: display data, manage local cache, sync.

### 7.3 Server Wins for Sync Conflicts
The backend is the source of truth. The only user-generated data is:
- URL sources (list of RSS feeds / homepages)
- Preference vectors (title + description)

Both are small and infrequently modified. Last-write-wins with server timestamp is sufficient.

### 7.4 Authentication Architecture
Add JWT-based auth with refresh tokens. The mobile app stores the refresh token securely (iOS Keychain / Android Keystore). The sync API requires authentication. The existing endpoints remain for the web app (add session-based auth there).

---

## 8. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Capacitor WebView performance for UMAP with 10K points | Medium | Use canvas-based rendering (current D3 approach); fallback to showing top 1000 points |
| Large initial sync on cellular data | Medium | Show sync size estimate; allow Wi-Fi-only sync option |
| Cohere API cost scaling with users | Low | Batch embedding calls; cache query embeddings; set per-user limits |
| App Store rejection (WebView-only) | Low | Capacitor apps are generally accepted; add native splash/icons |
| Background sync reliability | Low | Don't rely on it; sync on app open is sufficient for news use case |
| Multi-user PostgreSQL scaling | Medium | Use row-level security or schema-per-tenant in managed Postgres |

---

## 9. Summary

| Approach | Feasible? | Effort | Offline? | Billing Model |
|----------|-----------|--------|----------|---------------|
| **Fully on-device** | No | — | — | — |
| **Capacitor wrapper + minimal backend** | Yes | 5-8 weeks | Yes (read-only) | Backend subscription |
| **React Native + minimal backend** | Yes | 10-14 weeks | Yes (read-only) | Backend subscription |
| **Keep web-only, add PWA** | Yes | 1-2 weeks | Partial | Backend subscription |

**Recommended path**: Capacitor wrapper (Option A) with a consolidated single-process backend. This maximizes code reuse, delivers offline reading capability, and creates a clean billing boundary where users pay for the backend crawling/embedding service.

The backend becomes the product: "We crawl your news sources, cluster them semantically, and deliver them to your phone." The mobile app is the delivery mechanism.
