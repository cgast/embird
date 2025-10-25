# EmBird Development Roadmap

## ✅ Completed: API Documentation (Phase 1)

### What Was Delivered

#### 1. Comprehensive Pydantic Schemas (`app/schemas/`)
- **Common schemas**: Error handling, pagination, health checks
- **News schemas**: Complete validation for all news endpoints
- **URL schemas**: Source management with validation
- **Preference schemas**: User interest vectors
- **Total:** 5 new schema modules with 25+ validated models

#### 2. Full OpenAPI Documentation
- **Swagger UI**: Interactive API docs at `/api/docs`
- **ReDoc**: Beautiful documentation at `/api/redoc`
- **Detailed descriptions**: Every endpoint fully documented
- **Examples**: Request/response examples for all endpoints
- **Status codes**: Proper HTTP status code handling
- **Error models**: Standardized error responses

#### 3. Enhanced API Routes
- **Complete rewrite** of `app/routes/api.py`
- **Health check endpoint**: Monitor system services
- **15+ endpoints** fully documented:
  - Health: 1 endpoint
  - Sources: 4 endpoints
  - News: 6 endpoints
  - Preferences: 5 endpoints

#### 4. Documentation
- **API.md**: Complete API usage guide with examples
- **Interactive docs**: Available at runtime
- **Quick start**: Getting started examples

### Benefits Achieved

✅ **Type Safety**: Full request/response validation
✅ **Developer Experience**: Interactive API exploration
✅ **Error Handling**: Standardized, helpful errors
✅ **Headless Ready**: EmBird can now be used as pure API
✅ **Integration Ready**: Easy for external apps to consume

---

## 🎯 Designed: News Normalization Service (Phase 2)

### Vision

Transform EmBird into a **bias-free, fact-based news platform** that:
1. **Removes bias** from news articles
2. **Strips clickbait** and sensationalism
3. **Extracts structured facts** into machine-readable format
4. **Enables cross-source comparison** to find consensus

### Architecture Highlights

#### Database Extensions (5 New Tables)

```
normalized_news      → Processed articles with frontmatter
entities            → People, orgs, locations, products
news_entities       → Links articles to entities
events              → Canonical event descriptions
event_articles      → Links events to coverage
```

#### Structured Frontmatter Schema

Every normalized article gets structured metadata:

```json
{
  "subjects": ["Who is doing it"],
  "objects": ["Who/what is affected"],
  "action": {"What happened"},
  "effect": {"Result/impact"},
  "datetime": {"When it occurred"},
  "location": {"Where it happened"},
  "claims": ["Verifiable facts"],
  "quotes": ["Direct quotations"],
  "context": {"Background info"}
}
```

#### 6-Stage Processing Pipeline

1. **Bias Detection** → Identify emotional/loaded language
2. **Entity Extraction** → Extract named entities
3. **Event Extraction** → Identify core events
4. **Frontmatter Generation** → Create structured data
5. **Title/Summary Normalization** → Rewrite factually
6. **Quality Check** → Validate accuracy

#### Example Transformation

**Before (Biased/Clickbait):**
> "MIND-BLOWING! Apple's GAME-CHANGING iPhone REVOLUTIONIZES Everything! 🤯"

**After (Normalized):**
> "Apple announces iPhone 16 Pro with new camera sensor technology"

**Extracted:**
- Subject: Apple Inc.
- Object: iPhone 16 Pro
- Action: announce/release
- Claims: 1-inch sensor, $1,199, Nov 1 launch
- Bias score: 0.89 → 0.05
- Clickbait score: 0.95 → 0.10

### New API Endpoints (Planned)

#### Normalization
```
POST   /api/news/{id}/normalize      → Process article
GET    /api/news/{id}/normalized     → Get normalized version
GET    /api/news/normalized          → List all normalized
```

#### Entities
```
GET    /api/entities                 → List all entities
GET    /api/entities/{id}/news       → Get entity's articles
GET    /api/entities/search          → Search entities
```

#### Events
```
GET    /api/events                   → List canonical events
GET    /api/events/{id}              → Get event details
POST   /api/events/compare           → Compare sources
```

### Use Cases Enabled

1. **Objective Consumption** → Read news without bias
2. **Source Comparison** → See how coverage differs
3. **Entity Tracking** → Follow people/orgs across sources
4. **Structured Queries** → "Show all Microsoft announcements in Q4"
5. **Research** → Build knowledge graphs
6. **Fact Checking** → Verify claims across sources
7. **Timeline Construction** → Track story evolution

### LLM Strategy

**Primary**: Claude 3.5 Sonnet (best for bias detection)
**Fallback**: GPT-4o (faster, cheaper)
**Local**: Llama 3.1 70B via Ollama (privacy-focused)

**Cost Estimates:**
- $0.02-0.05 per article (Claude)
- $0.01-0.03 per article (GPT-4o)
- $15-40/day for 1000 articles

### Multi-Source Event Merging

Example: Gas explosion story

```
Source A (Breaking24):  "MASSIVE EXPLOSION! Multiple casualties feared!"
Source B (LocalNews):   "Gas line rupture causes explosion, 3 injured"
Source C (StateWire):   "Downtown evacuated after gas explosion"

→ Normalized Event:
  "Natural gas line rupture at 123 Main St caused explosion,
   resulting in 3 minor injuries"

→ Source Analysis:
  - Breaking24: Bias 0.78, Clickbait 0.91, Accuracy: Low
  - LocalNews:  Bias 0.15, Clickbait 0.22, Accuracy: High ✓
  - StateWire:  Bias 0.08, Clickbait 0.12, Accuracy: High ✓

→ Consensus Facts:
  ✓ Gas line rupture (2 sources)
  ✓ 3 people injured (2 sources)
  ✓ Injuries minor (2 sources)
  ✓ No fatalities (1 source)
```

---

## 📋 Implementation Roadmap

### Phase 2A: Normalization Foundation (Weeks 1-2)

**Week 1: Database & Infrastructure**
- [ ] Create database migrations for 5 new tables
- [ ] Set up entity extraction service
- [ ] Implement LLM service abstraction (Claude/GPT-4/Ollama)
- [ ] Create background job queue (Celery + Redis)

**Week 2: Core Pipeline**
- [ ] Implement bias detection stage
- [ ] Implement entity extraction stage
- [ ] Build frontmatter generation
- [ ] Create title/summary normalization

### Phase 2B: Processing & API (Weeks 3-4)

**Week 3: Pipeline Completion**
- [ ] Implement event extraction
- [ ] Build quality validation
- [ ] Create entity linking/resolution
- [ ] Add event merging logic

**Week 4: API Endpoints**
- [ ] Build normalization endpoints
- [ ] Create entity endpoints
- [ ] Implement event endpoints
- [ ] Add source comparison API

### Phase 2C: Advanced Features (Weeks 5-6)

**Week 5: Intelligence**
- [ ] Event clustering across sources
- [ ] Consensus fact extraction
- [ ] Source credibility scoring
- [ ] Timeline generation

**Week 6: Polish**
- [ ] Prompt optimization
- [ ] Performance tuning
- [ ] Cost optimization (caching)
- [ ] Comprehensive testing

### Phase 2D: Production (Weeks 7-8)

**Week 7: Deployment**
- [ ] Production deployment
- [ ] Monitoring & alerting
- [ ] Batch processing for historical articles
- [ ] Load testing

**Week 8: Documentation & Launch**
- [ ] User documentation
- [ ] API examples
- [ ] Blog post/announcement
- [ ] Public demo

---

## 🚀 Future Phases (Phase 3+)

### Phase 3: Advanced Analytics
- **Temporal Analysis**: Track story evolution over time
- **Sentiment Tracking**: Monitor sentiment about entities
- **Fact Verification**: Cross-reference with fact-check databases
- **Topic Modeling**: Advanced clustering

### Phase 4: User Features
- **Custom Normalizations**: User-adjustable bias thresholds
- **Annotations**: Community fact-checking
- **Alerts**: Notify on entity/event updates
- **Exports**: JSON-LD, RSS with frontmatter

### Phase 5: Scale & Polish
- **Multi-language**: Support non-English articles
- **Audio/Video**: Process podcast/video transcripts
- **Real-time**: Live normalization stream
- **API v2**: GraphQL interface

---

## 📊 Success Metrics

### Quality Metrics
- **Bias Reduction**: 80%+ reduction in bias scores
- **Factual Accuracy**: 95%+ accurate normalizations
- **Entity Accuracy**: 90%+ correct entity extraction
- **Event Accuracy**: 85%+ correct event descriptions

### Performance Metrics
- **Processing Speed**: < 30 seconds per article
- **API Latency**: < 2 seconds for normalized views
- **LLM Success Rate**: > 95% completions
- **Cost Efficiency**: < $0.05 per article average

### User Metrics
- **Preference**: 70%+ prefer normalized over raw
- **Engagement**: 2x time on normalized articles
- **Comparison Usage**: 40%+ use source comparison
- **Entity Exploration**: 30%+ explore entities

---

## 💡 Strategic Vision

### Short Term (3 months)
EmBird becomes a **headless news API** with:
- Comprehensive OpenAPI documentation ✅
- Bias-free normalized content 🎯
- Structured fact extraction 🎯
- Multi-source comparison 🎯

### Medium Term (6 months)
EmBird becomes **news intelligence platform**:
- Entity tracking across sources
- Event timeline construction
- Source credibility scoring
- Automated fact-checking

### Long Term (12+ months)
EmBird becomes **news infrastructure layer**:
- Knowledge graph generation
- AI training data (bias-free)
- Research platform
- Journalism tool

---

## 🎯 Unique Value Proposition

**What makes EmBird different:**

1. **Bias-Free by Design**
   - Not just aggregation, but normalization
   - Explicit bias removal process
   - Transparent transformations

2. **Structured Facts**
   - Machine-readable frontmatter
   - Entity-action-object model
   - Verifiable claims tracking

3. **Multi-Source Intelligence**
   - Consensus fact extraction
   - Source comparison
   - Coverage completeness analysis

4. **Open Source & Self-Hosted**
   - Full control over data
   - Privacy-preserving
   - Customizable normalization rules

5. **API-First**
   - Headless service
   - Easy integration
   - Comprehensive documentation

---

## 🔧 Technical Excellence

### Current State
✅ Clean microservices architecture
✅ Modern Python async (FastAPI)
✅ Vector embeddings (Cohere + FAISS)
✅ PostgreSQL + pgvector
✅ Docker Compose deployment
✅ Full OpenAPI documentation

### Next Level
🎯 LLM integration (Claude/GPT-4)
🎯 Advanced NLP (entity extraction)
🎯 Background job processing
🎯 Caching & optimization
🎯 Comprehensive testing
🎯 Production monitoring

---

## 🤝 Getting Started

### Current API (v1.0)

**Start the service:**
```bash
docker-compose up -d
```

**Access documentation:**
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

**Add a source:**
```bash
curl -X POST http://localhost:8000/api/urls \
  -H "Content-Type: application/json" \
  -d '{"url": "https://techcrunch.com/feed/", "type": "rss"}'
```

**Search semantically:**
```bash
curl "http://localhost:8000/api/news/search?query=AI&limit=10"
```

### Upcoming: Normalization API (v2.0)

**Normalize an article:**
```bash
curl -X POST http://localhost:8000/api/news/123/normalize
```

**Get normalized version:**
```bash
curl http://localhost:8000/api/news/123/normalized
```

**Compare sources:**
```bash
curl -X POST http://localhost:8000/api/events/compare \
  -d '{"event_id": 456}'
```

---

## 📚 Documentation

- **README.md** - Project overview
- **docs/API.md** - Complete API reference
- **docs/NORMALIZATION_SERVICE.md** - Architecture design
- **docs/NORMALIZATION_EXAMPLES.md** - Real-world examples
- **docs/ROADMAP.md** - This document
- **/api/docs** - Interactive Swagger UI
- **/api/redoc** - Beautiful ReDoc

---

## 🎉 Summary

**What we accomplished today:**

1. ✅ Transformed EmBird into a well-documented headless API service
2. ✅ Created comprehensive Pydantic schemas for all endpoints
3. ✅ Added full OpenAPI/Swagger support
4. ✅ Designed complete architecture for bias-free news normalization
5. ✅ Documented 4 detailed examples of normalization
6. ✅ Created implementation roadmap (8 weeks to production)

**EmBird is now positioned as:**
- 🎯 Modern news aggregation platform
- 🎯 Headless API service (ready for integrations)
- 🎯 Future: Bias-free news intelligence layer

**Next steps:**
1. Review and approve architecture design
2. Begin Phase 2A implementation (database + LLM integration)
3. Iterate on normalization examples
4. Ship v2.0 with normalization service! 🚀

---

*Generated with [Claude Code](https://claude.com/claude-code)*
