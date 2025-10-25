# News Normalization Service - Architecture Design

## Vision

Transform EmBird from a news aggregation platform into a **bias-free, fact-based news service** that provides normalized, structured news data. The normalization service will strip away clickbait, remove editorial bias, and extract verifiable facts into a structured format.

## Objectives

1. **Remove Bias**: Eliminate subjective language, emotional triggers, and editorial slant
2. **Strip Clickbait**: Convert sensational headlines into factual descriptions
3. **Extract Facts**: Identify and structure verifiable information
4. **Generate Frontmatter**: Create machine-readable metadata with:
   - **Subject** (entities): Who is involved
   - **Object** (entities): Who/what is affected
   - **Action**: What happened
   - **Effect**: What was the result/impact
   - **DateTime**: When it happened
   - **Location**: Where it happened (if applicable)
5. **Enable Comparison**: Allow users to compare how different sources cover the same event

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     EmBird Platform                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐│
│  │ Crawler  │→ │ Embedder │→ │   FAISS  │  │ Normalization││
│  │ Service  │  │ Service  │  │ Clusters │  │   Service    ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘│
│       │             │                              │        │
│       ↓             ↓                              ↓        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │            PostgreSQL Database                           ││
│  │  - news (raw articles)                                  ││
│  │  - normalized_news (processed articles)                 ││
│  │  - entities (subject/object entities)                   ││
│  │  - events (normalized event descriptions)               ││
│  │  - source_comparisons (cross-source analysis)           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                External LLM API                         ││
│  │  - Claude API (Anthropic) - Primary                     ││
│  │  - GPT-4 API (OpenAI) - Fallback                        ││
│  │  - Local LLM (Ollama) - Optional                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema Extensions

### 1. `normalized_news` Table

Stores the normalized/de-biased version of articles.

```sql
CREATE TABLE normalized_news (
    id SERIAL PRIMARY KEY,
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,

    -- Normalized content
    normalized_title TEXT NOT NULL,           -- De-biased, factual title
    normalized_summary TEXT,                  -- Factual summary without opinion

    -- Structured frontmatter (JSON)
    frontmatter JSONB NOT NULL,               -- See schema below

    -- Bias analysis
    original_bias_score FLOAT,                -- 0.0 (neutral) to 1.0 (highly biased)
    clickbait_score FLOAT,                    -- 0.0 (factual) to 1.0 (pure clickbait)
    removed_phrases TEXT[],                   -- Biased phrases that were removed

    -- Processing metadata
    llm_model TEXT NOT NULL,                  -- Model used (e.g., "claude-3-5-sonnet")
    processing_version TEXT NOT NULL,         -- Version of normalization algorithm
    confidence_score FLOAT,                   -- LLM's confidence in normalization

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    UNIQUE(news_id),
    INDEX idx_normalized_frontmatter ON normalized_news USING GIN (frontmatter)
);
```

### 2. `entities` Table

Stores extracted named entities (people, organizations, locations).

```sql
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                       -- 'PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', etc.
    canonical_name TEXT,                      -- Normalized name (e.g., "USA" → "United States")
    aliases TEXT[],                           -- Known aliases
    wikipedia_url TEXT,                       -- External reference
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(name, type),
    INDEX idx_entity_type ON entities(type)
);
```

### 3. `news_entities` Table

Links news articles to entities (many-to-many).

```sql
CREATE TABLE news_entities (
    id SERIAL PRIMARY KEY,
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                       -- 'SUBJECT', 'OBJECT', 'MENTIONED'
    sentiment TEXT,                           -- 'POSITIVE', 'NEUTRAL', 'NEGATIVE', null

    UNIQUE(news_id, entity_id, role),
    INDEX idx_news_entities_news ON news_entities(news_id),
    INDEX idx_news_entities_entity ON news_entities(entity_id),
    INDEX idx_news_entities_role ON news_entities(role)
);
```

### 4. `events` Table

Stores normalized event descriptions that may span multiple articles.

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,

    -- Event description
    canonical_description TEXT NOT NULL,      -- Neutral description of event
    event_type TEXT,                          -- 'ANNOUNCEMENT', 'INCIDENT', 'POLICY', etc.

    -- Event metadata
    event_date DATE,                          -- When it happened
    event_datetime TIMESTAMP WITH TIME ZONE,  -- Precise time if known
    location TEXT,                            -- Where it happened

    -- Clustering
    embedding VECTOR(1024),                   -- Embedding of canonical description

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_event_date ON events(event_date),
    INDEX idx_event_embedding ON events USING ivfflat (embedding vector_cosine_ops)
);
```

### 5. `event_articles` Table

Links articles to events (many-to-many, since one article can cover multiple events).

```sql
CREATE TABLE event_articles (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    news_id INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,

    -- Coverage analysis
    coverage_completeness FLOAT,             -- How completely this article covers the event
    unique_facts TEXT[],                     -- Facts mentioned only in this source

    UNIQUE(event_id, news_id),
    INDEX idx_event_articles_event ON event_articles(event_id),
    INDEX idx_event_articles_news ON event_articles(news_id)
);
```

---

## Frontmatter Schema

The `frontmatter` JSONB field will follow this structure:

```json
{
  "version": "1.0",
  "subjects": [
    {
      "entity": "Anthropic",
      "type": "ORG",
      "entity_id": 42
    },
    {
      "entity": "Dario Amodei",
      "type": "PERSON",
      "entity_id": 123
    }
  ],
  "objects": [
    {
      "entity": "Claude 3.5 Sonnet",
      "type": "PRODUCT",
      "entity_id": 456
    }
  ],
  "action": {
    "verb": "announce",
    "description": "announced the release of",
    "tense": "past"
  },
  "effect": {
    "description": "new AI model with improved capabilities",
    "impact_level": "significant",
    "affected_entities": []
  },
  "datetime": {
    "extracted": "2025-10-25T10:00:00Z",
    "precision": "hour",
    "is_estimate": false
  },
  "location": {
    "place": "San Francisco, CA",
    "country": "United States",
    "coordinates": null
  },
  "claims": [
    {
      "claim": "Model outperforms GPT-4 on coding tasks",
      "verifiable": true,
      "source": "benchmark results",
      "confidence": "high"
    }
  ],
  "quotes": [
    {
      "text": "We're excited to introduce...",
      "speaker": "Dario Amodei",
      "speaker_entity_id": 123
    }
  ],
  "context": {
    "background": "Part of ongoing AI model competition",
    "related_events": [234, 567]
  }
}
```

---

## Normalization Pipeline

### Phase 1: Article Ingestion
```
Raw Article → Parse HTML → Extract Content → Store in `news` table
```

### Phase 2: Normalization Processing

```python
class NormalizationPipeline:
    """
    Multi-stage pipeline for normalizing news articles.
    """

    async def normalize_article(self, news_item: NewsItem) -> NormalizedNews:
        """
        Process a single article through normalization pipeline.
        """
        # Stage 1: Bias Detection
        bias_analysis = await self.analyze_bias(news_item)

        # Stage 2: Entity Extraction
        entities = await self.extract_entities(news_item)

        # Stage 3: Event Extraction
        events = await self.extract_events(news_item)

        # Stage 4: Frontmatter Generation
        frontmatter = await self.generate_frontmatter(
            news_item,
            entities,
            events
        )

        # Stage 5: Title/Summary Normalization
        normalized_title = await self.normalize_title(
            news_item.title,
            frontmatter
        )
        normalized_summary = await self.normalize_summary(
            news_item.summary,
            frontmatter
        )

        # Stage 6: Quality Check
        validation = await self.validate_normalization(
            news_item,
            normalized_title,
            normalized_summary,
            frontmatter
        )

        return NormalizedNews(
            news_id=news_item.id,
            normalized_title=normalized_title,
            normalized_summary=normalized_summary,
            frontmatter=frontmatter,
            original_bias_score=bias_analysis.bias_score,
            clickbait_score=bias_analysis.clickbait_score,
            removed_phrases=bias_analysis.removed_phrases,
            confidence_score=validation.confidence_score,
            llm_model=self.model_name,
            processing_version=self.version
        )
```

### Stage Details

#### Stage 1: Bias Detection

Uses LLM to analyze:
- **Emotional language**: "shocking", "outrageous", "incredible"
- **Loaded terms**: "regime", "freedom fighters" vs "terrorists"
- **Exaggeration**: "completely destroyed", "worst ever"
- **Subjective adjectives**: "beautiful", "terrible", "amazing"
- **One-sided framing**: Only presenting one perspective

**Prompt Template:**
```
Analyze this news article for bias and clickbait:

Title: {title}
Summary: {summary}

Provide:
1. Bias score (0.0-1.0)
2. Clickbait score (0.0-1.0)
3. List of biased/clickbait phrases
4. Explanation of detected bias types

Output as JSON.
```

#### Stage 2: Entity Extraction

Extract and normalize entities:
- **People**: "Elon Musk", "President Biden", "CEO of Apple"
- **Organizations**: "Microsoft", "EU", "United Nations"
- **Locations**: "Washington DC", "Ukraine", "Silicon Valley"
- **Products**: "iPhone 15", "Claude AI", "Tesla Model 3"

Uses:
- Named Entity Recognition (NER)
- Entity linking to canonical names
- Coreference resolution (he/she → actual name)

**Prompt Template:**
```
Extract all entities from this article:

Title: {title}
Content: {summary}

For each entity, provide:
- Name
- Type (PERSON, ORG, GPE, PRODUCT, etc.)
- Canonical name (normalized)
- Role (SUBJECT, OBJECT, MENTIONED)

Output as JSON array.
```

#### Stage 3: Event Extraction

Identify the core event(s):
- What happened?
- When did it happen?
- Where did it happen?
- Who was involved?

**Prompt Template:**
```
Extract the main event(s) from this article:

Title: {title}
Content: {summary}

For each event, provide:
1. Neutral description (no bias)
2. Event type (ANNOUNCEMENT, INCIDENT, POLICY, etc.)
3. Date/time (extracted or estimated)
4. Location (if mentioned)
5. Participants (subjects and objects)

Output as JSON array.
```

#### Stage 4: Frontmatter Generation

Combine extracted information into structured frontmatter:

**Prompt Template:**
```
Generate structured frontmatter for this article:

Title: {title}
Content: {summary}
Entities: {entities_json}
Events: {events_json}

Create a JSON object with:
- subjects: Primary actors
- objects: Affected entities
- action: What happened (verb + description)
- effect: Result/impact
- datetime: When it occurred
- location: Where it occurred
- claims: Verifiable statements made
- quotes: Direct quotations
- context: Background information

Be factual and neutral.
```

#### Stage 5: Title/Summary Normalization

Rewrite content to be factual and neutral:

**Original Title:**
```
"SHOCKING: Tech Giant Faces DEVASTATING Lawsuit That Could DESTROY Everything!"
```

**Normalized Title:**
```
"Microsoft faces antitrust lawsuit from Department of Justice"
```

**Prompt Template:**
```
Rewrite this news title to be factual and neutral:

Original Title: {title}
Frontmatter: {frontmatter_json}

Requirements:
- Remove all bias and emotional language
- Remove clickbait elements
- State facts clearly
- Maintain accuracy
- Use active voice
- Keep it concise (< 100 chars)

Output only the normalized title.
```

#### Stage 6: Quality Check

Validate the normalization:
- Does normalized version preserve facts?
- Is frontmatter complete and accurate?
- Are entities correctly identified?
- Is the tone truly neutral?

**Prompt Template:**
```
Evaluate this normalization:

Original: {original_title}
Normalized: {normalized_title}
Frontmatter: {frontmatter_json}

Rate on:
1. Factual accuracy (0.0-1.0)
2. Neutrality (0.0-1.0)
3. Completeness (0.0-1.0)

Overall confidence score (0.0-1.0):

Provide brief explanation of any concerns.
Output as JSON.
```

---

## LLM Integration

### Model Selection Strategy

**Primary: Claude 3.5 Sonnet (Anthropic)**
- Best for nuanced bias detection
- Strong reasoning for fact extraction
- Excellent JSON output formatting
- Good at following complex instructions

**Fallback: GPT-4o (OpenAI)**
- Fast and cost-effective
- Good entity extraction
- Reliable JSON output

**Local Option: Llama 3.1 70B (via Ollama)**
- For privacy-sensitive deployments
- No API costs
- Requires GPU resources

### API Integration

```python
class LLMService:
    """
    Abstraction layer for LLM providers.
    """

    def __init__(self):
        self.providers = {
            'claude': ClaudeProvider(),
            'gpt4': GPT4Provider(),
            'local': LocalProvider()
        }
        self.primary = 'claude'
        self.fallback = 'gpt4'

    async def complete(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4000
    ) -> str:
        """
        Send completion request with automatic fallback.
        """
        try:
            return await self.providers[self.primary].complete(
                prompt, system, temperature, max_tokens
            )
        except Exception as e:
            logger.warning(f"Primary LLM failed: {e}, trying fallback")
            return await self.providers[self.fallback].complete(
                prompt, system, temperature, max_tokens
            )
```

### Prompt Engineering Best Practices

1. **Use structured output**: Always request JSON for parseable results
2. **Few-shot examples**: Include 2-3 examples in prompt for consistency
3. **Temperature = 0.0**: For factual, deterministic output
4. **Validate output**: Parse and validate JSON before storing
5. **Retry logic**: Retry with corrected prompt if JSON parsing fails

---

## API Endpoints (New)

### Normalization Endpoints

#### `POST /api/news/{news_id}/normalize`

Trigger normalization for a specific article.

**Request:**
```json
{
  "force": false,  // Re-normalize even if already processed
  "model": "claude"  // Optional: specify LLM model
}
```

**Response:**
```json
{
  "news_id": 12345,
  "status": "processing",
  "job_id": "norm-12345-abc",
  "estimated_completion": "2025-10-25T12:05:00Z"
}
```

#### `GET /api/news/{news_id}/normalized`

Get normalized version of an article.

**Response:**
```json
{
  "id": 678,
  "news_id": 12345,
  "normalized_title": "Microsoft announces new AI model",
  "normalized_summary": "Microsoft Corporation released...",
  "frontmatter": { /* full frontmatter JSON */ },
  "original_bias_score": 0.72,
  "clickbait_score": 0.85,
  "confidence_score": 0.91,
  "created_at": "2025-10-25T12:00:00Z"
}
```

#### `GET /api/news/normalized`

List all normalized articles with filtering.

**Query Parameters:**
- `entity_id`: Filter by entity involvement
- `entity_name`: Filter by entity name
- `event_type`: Filter by event type
- `date_from`, `date_to`: Filter by event date
- `min_confidence`: Minimum confidence score

**Response:**
```json
{
  "items": [
    {
      "id": 678,
      "normalized_title": "...",
      "frontmatter": { /* ... */ }
    }
  ],
  "total": 150,
  "offset": 0,
  "limit": 100
}
```

### Entity Endpoints

#### `GET /api/entities`

List all extracted entities.

**Response:**
```json
[
  {
    "id": 42,
    "name": "Microsoft",
    "type": "ORG",
    "canonical_name": "Microsoft Corporation",
    "aliases": ["MSFT", "Microsoft Corp"],
    "article_count": 245
  }
]
```

#### `GET /api/entities/{entity_id}/news`

Get all news articles mentioning an entity.

**Query Parameters:**
- `role`: Filter by role (SUBJECT, OBJECT, MENTIONED)
- `date_from`, `date_to`: Date range

#### `GET /api/entities/search`

Search for entities by name.

**Query:** `?q=microsoft&type=ORG`

### Event Endpoints

#### `GET /api/events`

List all normalized events.

**Response:**
```json
[
  {
    "id": 234,
    "canonical_description": "Microsoft announced quarterly earnings",
    "event_type": "ANNOUNCEMENT",
    "event_date": "2025-10-25",
    "location": "Redmond, WA",
    "article_count": 15,
    "sources": ["TechCrunch", "Reuters", "Bloomberg"]
  }
]
```

#### `GET /api/events/{event_id}`

Get details for a specific event.

**Response:**
```json
{
  "id": 234,
  "canonical_description": "Microsoft announced quarterly earnings",
  "event_type": "ANNOUNCEMENT",
  "event_date": "2025-10-25",
  "articles": [
    {
      "news_id": 12345,
      "source": "TechCrunch",
      "coverage_completeness": 0.85,
      "unique_facts": ["Revenue grew 15%"]
    }
  ]
}
```

#### `POST /api/events/compare`

Compare how different sources covered the same event.

**Request:**
```json
{
  "event_id": 234
}
```

**Response:**
```json
{
  "event_id": 234,
  "canonical_description": "Microsoft announced earnings",
  "sources": [
    {
      "source": "TechCrunch",
      "bias_score": 0.3,
      "unique_facts": ["Stock price rose 5%"],
      "sentiment": "positive"
    },
    {
      "source": "Reuters",
      "bias_score": 0.1,
      "unique_facts": [],
      "sentiment": "neutral"
    }
  ],
  "consensus_facts": [
    "Revenue: $56.5 billion",
    "Profit: $22.3 billion"
  ],
  "disputed_facts": [],
  "coverage_matrix": {
    "revenue": ["TechCrunch", "Reuters", "Bloomberg"],
    "profit": ["TechCrunch", "Reuters"],
    "stock_price": ["TechCrunch"]
  }
}
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Database schema extensions
- [ ] LLM service abstraction layer
- [ ] Basic normalization pipeline
- [ ] Bias detection prototype

### Phase 2: Core Normalization (Weeks 3-4)
- [ ] Entity extraction and linking
- [ ] Event extraction
- [ ] Frontmatter generation
- [ ] Title/summary normalization
- [ ] Quality validation

### Phase 3: API & Integration (Week 5)
- [ ] REST API endpoints
- [ ] Background job queue (Celery + Redis)
- [ ] Batch processing for existing articles
- [ ] Monitoring and metrics

### Phase 4: Advanced Features (Week 6-7)
- [ ] Event clustering (group related articles)
- [ ] Source comparison
- [ ] Consensus fact extraction
- [ ] Timeline generation

### Phase 5: Refinement (Week 8)
- [ ] Prompt optimization
- [ ] Performance tuning
- [ ] Cost optimization (caching, batch processing)
- [ ] Documentation and examples

---

## Performance Considerations

### Costs

**LLM API Costs (estimated per article):**
- Claude 3.5 Sonnet: ~$0.02-0.05 per article
- GPT-4o: ~$0.01-0.03 per article
- Local (Ollama): Free (but requires GPU)

**Processing 1000 articles/day:**
- Claude: $20-50/day
- GPT-4o: $10-30/day
- Mix (70% GPT-4o, 30% Claude): ~$15-40/day

### Optimization Strategies

1. **Batch Processing**: Process similar articles together
2. **Caching**: Cache entity resolutions and event descriptions
3. **Selective Processing**: Only normalize high-value articles
4. **Queue Priorities**: Process breaking news first
5. **Rate Limiting**: Respect API rate limits, use exponential backoff

### Scalability

**For 10,000 articles/day:**
- Use background job queue (Celery)
- Horizontal scaling of workers
- Database read replicas
- Redis caching layer
- LLM request batching

---

## Success Metrics

### Quality Metrics

1. **Bias Reduction**: Average bias score before vs after
2. **Clickbait Elimination**: Clickbait score reduction
3. **Factual Accuracy**: Manual validation sample (95%+ accurate)
4. **Entity Accuracy**: Correct entity extraction (90%+)
5. **Event Accuracy**: Correct event description (85%+)

### Performance Metrics

1. **Processing Speed**: < 30 seconds per article
2. **API Response Time**: < 2 seconds for normalized view
3. **LLM Success Rate**: > 95% successful completions
4. **Cost per Article**: < $0.05 average

### User Metrics

1. **Normalized vs Raw Preference**: % users preferring normalized
2. **Engagement**: Time spent on normalized articles
3. **Comparison Usage**: % users using source comparison
4. **Entity Exploration**: % users exploring entities

---

## Future Enhancements

### Phase 2+ Features

1. **Fact Verification**: Cross-reference with fact-checking databases
2. **Source Credibility Scoring**: Rate sources by accuracy over time
3. **Temporal Analysis**: Track how stories evolve over time
4. **Sentiment Tracking**: Monitor sentiment changes about entities
5. **Topic Modeling**: Advanced clustering by topics
6. **Multi-language Support**: Normalize non-English articles
7. **Audio/Video Processing**: Normalize podcast/video transcripts
8. **User Annotations**: Allow users to flag inaccuracies
9. **Export Formats**: JSON-LD, RSS, ATOM with frontmatter
10. **API Webhooks**: Notify external systems of new normalized articles

---

## Ethical Considerations

### Transparency

- Always provide original article alongside normalized version
- Show what was changed and why
- Disclose LLM model and version used
- Provide confidence scores

### Bias Handling

- Acknowledge that normalization itself has bias
- Allow users to rate normalized versions
- Continuously improve based on feedback
- Provide appeal mechanism for incorrect normalization

### Privacy

- Don't store user reading preferences for normalized articles
- Anonymize usage analytics
- Provide opt-out for personalization

### Accountability

- Log all normalization decisions
- Allow human review of flagged articles
- Provide correction mechanism
- Regular audits of normalization quality

---

## Conclusion

The News Normalization Service will transform EmBird from a simple aggregator into an intelligent, bias-aware news platform. By extracting facts, removing bias, and structuring information, we enable users to:

1. **Consume news objectively** without editorial spin
2. **Compare sources** to understand different perspectives
3. **Track entities and events** across multiple sources
4. **Query structurally** (e.g., "Show me all actions by Microsoft in Q4 2025")
5. **Build on structured data** for further analysis

This positions EmBird as a **foundational infrastructure** for fact-based news consumption, research, and journalism.
