# News Normalization - Real-World Examples

## Example 1: Tech Announcement

### Original Article (Clickbait/Biased)

**Source:** TechClickbait.com

**Title:**
```
MIND-BLOWING! Apple's GAME-CHANGING New iPhone Feature Will COMPLETELY REVOLUTIONIZE Everything You Know About Smartphones! 🤯
```

**Summary:**
```
Apple has just dropped the most INCREDIBLE announcement of the decade! Their amazing new iPhone 16 Pro comes with an absolutely STUNNING feature that leaves competitors in the dust. Industry insiders are calling it a "total game-changer" that will make all other phones look like ancient relics. This revolutionary technology is set to DOMINATE the market and crush the competition!
```

### Normalized Version

**Title:**
```
Apple announces iPhone 16 Pro with new camera sensor technology
```

**Summary:**
```
Apple Inc. released the iPhone 16 Pro, featuring a 1-inch camera sensor. The device launches November 1, 2025, starting at $1,199.
```

**Frontmatter:**
```json
{
  "version": "1.0",
  "subjects": [
    {
      "entity": "Apple Inc.",
      "type": "ORG",
      "entity_id": 1001
    }
  ],
  "objects": [
    {
      "entity": "iPhone 16 Pro",
      "type": "PRODUCT",
      "entity_id": 5002
    }
  ],
  "action": {
    "verb": "announce",
    "description": "announced the release of",
    "tense": "past"
  },
  "effect": {
    "description": "new smartphone product with enhanced camera sensor",
    "impact_level": "moderate",
    "affected_entities": [
      {
        "entity": "smartphone market",
        "type": "MARKET"
      }
    ]
  },
  "datetime": {
    "extracted": "2025-10-25T10:00:00Z",
    "precision": "hour",
    "is_estimate": false
  },
  "location": {
    "place": "Cupertino, CA",
    "country": "United States"
  },
  "claims": [
    {
      "claim": "1-inch camera sensor",
      "verifiable": true,
      "source": "press release",
      "confidence": "high"
    },
    {
      "claim": "Launch date: November 1, 2025",
      "verifiable": true,
      "source": "press release",
      "confidence": "high"
    },
    {
      "claim": "Starting price: $1,199",
      "verifiable": true,
      "source": "press release",
      "confidence": "high"
    }
  ],
  "context": {
    "background": "Annual iPhone product refresh cycle",
    "related_events": []
  }
}
```

**Bias Analysis:**
```json
{
  "original_bias_score": 0.89,
  "clickbait_score": 0.95,
  "removed_phrases": [
    "MIND-BLOWING",
    "GAME-CHANGING",
    "COMPLETELY REVOLUTIONIZE",
    "most INCREDIBLE",
    "absolutely STUNNING",
    "total game-changer",
    "ancient relics",
    "DOMINATE",
    "crush the competition"
  ],
  "bias_types_detected": [
    "emotional_hyperbole",
    "capitalization_abuse",
    "superlative_overuse",
    "competitive_framing"
  ]
}
```

---

## Example 2: Political News

### Original Article (Biased)

**Source:** PartisanNews.com

**Title:**
```
Heroic Senator Fights Against Radical Proposal That Would Destroy American Values
```

**Summary:**
```
Courageous Senator John Smith took a brave stand yesterday against the dangerous and extreme legislation pushed by his out-of-touch opponents. The reckless proposal, which threatens to undermine our fundamental freedoms, was rightfully rejected by patriotic Americans who understand what's really at stake for our nation's future.
```

### Normalized Version

**Title:**
```
Senate votes down proposed healthcare legislation
```

**Summary:**
```
The U.S. Senate rejected proposed healthcare legislation with a 52-48 vote on October 24, 2025. Senator John Smith (R-TX) voted against the bill, which would have expanded Medicare eligibility to adults aged 55-65.
```

**Frontmatter:**
```json
{
  "version": "1.0",
  "subjects": [
    {
      "entity": "U.S. Senate",
      "type": "ORG",
      "entity_id": 2001
    },
    {
      "entity": "John Smith",
      "type": "PERSON",
      "entity_id": 3001,
      "role_description": "Senator (R-TX)"
    }
  ],
  "objects": [
    {
      "entity": "Healthcare legislation H.R. 1234",
      "type": "LEGISLATION",
      "entity_id": 4001
    },
    {
      "entity": "Medicare",
      "type": "PROGRAM",
      "entity_id": 4002
    }
  ],
  "action": {
    "verb": "reject",
    "description": "voted down",
    "tense": "past"
  },
  "effect": {
    "description": "legislation did not pass",
    "impact_level": "significant",
    "affected_entities": [
      {
        "entity": "adults aged 55-65",
        "type": "GROUP",
        "estimated_size": "approximately 30 million Americans"
      }
    ]
  },
  "datetime": {
    "extracted": "2025-10-24T15:30:00Z",
    "precision": "minute",
    "is_estimate": false
  },
  "location": {
    "place": "U.S. Capitol, Washington, DC",
    "country": "United States"
  },
  "claims": [
    {
      "claim": "Vote result: 52-48",
      "verifiable": true,
      "source": "Senate records",
      "confidence": "high"
    },
    {
      "claim": "Bill would expand Medicare eligibility to ages 55-65",
      "verifiable": true,
      "source": "bill text",
      "confidence": "high"
    },
    {
      "claim": "Senator John Smith voted against",
      "verifiable": true,
      "source": "Senate records",
      "confidence": "high"
    }
  ],
  "context": {
    "background": "Ongoing healthcare policy debate",
    "related_events": [1234, 5678]
  }
}
```

**Bias Analysis:**
```json
{
  "original_bias_score": 0.92,
  "clickbait_score": 0.67,
  "removed_phrases": [
    "Heroic",
    "Fights Against",
    "Radical",
    "Destroy American Values",
    "Courageous",
    "brave stand",
    "dangerous and extreme",
    "out-of-touch opponents",
    "reckless proposal",
    "threatens to undermine",
    "fundamental freedoms",
    "rightfully",
    "patriotic Americans"
  ],
  "bias_types_detected": [
    "partisan_language",
    "loaded_terms",
    "moral_framing",
    "us_vs_them_framing",
    "emotional_appeal"
  ]
}
```

---

## Example 3: Breaking News

### Original Articles (Multiple Sources)

#### Source A: Breaking24News.com

**Title:**
```
BREAKING: Massive Explosion Rocks Downtown - Multiple Casualties Feared!
```

**Summary:**
```
A huge explosion has devastated the downtown area. Eyewitnesses report scenes of absolute chaos with emergency services rushing to the scene. The full extent of casualties remains unknown but sources say it could be catastrophic.
```

#### Source B: LocalNewsNetwork.com

**Title:**
```
Gas Line Rupture Causes Explosion in Business District
```

**Summary:**
```
A natural gas line rupture caused an explosion at 123 Main Street this morning. Fire department spokesperson confirmed 3 injuries, none life-threatening. The building was evacuated and nearby businesses were asked to shelter in place. Investigation ongoing.
```

#### Source C: StateWireSe...
```

**Title:**
```
Downtown Building Evacuated After Gas Explosion, Three Injured
```

**Summary:**
```
Three people suffered minor injuries following a gas line explosion at a commercial building on Main Street. The incident occurred at approximately 9:45 AM. Authorities have secured the area and utility crews are working to shut off gas supply. No fatalities reported.
```

### Normalized Event (Merged)

**Canonical Description:**
```
Natural gas line rupture caused explosion at 123 Main Street, resulting in three minor injuries
```

**Frontmatter:**
```json
{
  "version": "1.0",
  "subjects": [],
  "objects": [
    {
      "entity": "123 Main Street building",
      "type": "LOCATION",
      "entity_id": 6001
    }
  ],
  "action": {
    "verb": "explode",
    "description": "natural gas line ruptured, causing explosion",
    "tense": "past"
  },
  "effect": {
    "description": "building damage, three people injured (minor)",
    "impact_level": "moderate",
    "affected_entities": [
      {
        "entity": "three individuals",
        "type": "PEOPLE",
        "injury_severity": "minor"
      },
      {
        "entity": "nearby businesses",
        "type": "BUSINESSES",
        "impact": "temporary evacuation"
      }
    ]
  },
  "datetime": {
    "extracted": "2025-10-25T09:45:00Z",
    "precision": "minute",
    "is_estimate": false
  },
  "location": {
    "place": "123 Main Street, Downtown Business District",
    "city": "Springfield",
    "state": "State",
    "country": "United States"
  },
  "claims": [
    {
      "claim": "Three people injured",
      "verifiable": true,
      "source": "fire department",
      "confidence": "high",
      "source_count": 3
    },
    {
      "claim": "Injuries were minor/non-life-threatening",
      "verifiable": true,
      "source": "fire department",
      "confidence": "high",
      "source_count": 2
    },
    {
      "claim": "No fatalities",
      "verifiable": true,
      "source": "authorities",
      "confidence": "high",
      "source_count": 1
    },
    {
      "claim": "Cause: natural gas line rupture",
      "verifiable": true,
      "source": "fire department",
      "confidence": "high",
      "source_count": 2
    }
  ],
  "context": {
    "background": "Urban infrastructure incident",
    "investigation_status": "ongoing"
  }
}
```

**Source Comparison:**

```json
{
  "event_id": 7001,
  "sources": [
    {
      "source": "Breaking24News.com",
      "bias_score": 0.78,
      "clickbait_score": 0.91,
      "accuracy": "low",
      "unique_facts": [],
      "inaccuracies": [
        "Used 'Multiple Casualties Feared' - actual: 3 minor injuries",
        "Used 'Massive' and 'Devastated' - exaggerated scale"
      ],
      "sentiment": "alarming",
      "completeness": 0.3
    },
    {
      "source": "LocalNewsNetwork.com",
      "bias_score": 0.15,
      "clickbait_score": 0.22,
      "accuracy": "high",
      "unique_facts": [
        "Specific address: 123 Main Street",
        "Fire department quote",
        "Shelter-in-place order for nearby businesses"
      ],
      "inaccuracies": [],
      "sentiment": "neutral",
      "completeness": 0.85
    },
    {
      "source": "StateWireService.com",
      "bias_score": 0.08,
      "clickbait_score": 0.12,
      "accuracy": "high",
      "unique_facts": [
        "Precise time: 9:45 AM",
        "Utility crews shutting off gas",
        "Explicit 'no fatalities' statement"
      ],
      "inaccuracies": [],
      "sentiment": "neutral",
      "completeness": 0.80
    }
  ],
  "consensus_facts": [
    "Gas line rupture caused explosion",
    "Three people injured",
    "Injuries were minor",
    "No fatalities",
    "Building evacuated",
    "Investigation ongoing"
  ],
  "disputed_facts": [],
  "coverage_matrix": {
    "gas_line_cause": ["LocalNewsNetwork", "StateWireService"],
    "three_injured": ["LocalNewsNetwork", "StateWireService"],
    "minor_injuries": ["LocalNewsNetwork", "StateWireService"],
    "no_fatalities": ["StateWireService"],
    "specific_address": ["LocalNewsNetwork"],
    "precise_time": ["StateWireService"],
    "evacuation": ["LocalNewsNetwork", "StateWireService"]
  },
  "recommended_source": "LocalNewsNetwork.com",
  "recommendation_reason": "Most complete, accurate, and neutral coverage"
}
```

---

## Example 4: Financial News

### Original Article

**Source:** InvestorBuzz.com

**Title:**
```
Tesla Stock SOARS After Musk's Brilliant Move Stuns Wall Street Analysts!
```

**Summary:**
```
Elon Musk did it again! The visionary CEO's genius announcement sent Tesla shares skyrocketing in after-hours trading, proving once again why he's the greatest entrepreneur of our generation. Critics and short-sellers were left speechless as the stock surged, with experts predicting it could moon even further!
```

### Normalized Version

**Title:**
```
Tesla stock rises 4.2% following new factory announcement
```

**Summary:**
```
Tesla, Inc. shares increased 4.2% to $245.80 in after-hours trading on October 25, 2025, following CEO Elon Musk's announcement of a planned manufacturing facility in Texas. The company stated the factory would produce electric vehicle batteries with production beginning in Q3 2026.
```

**Frontmatter:**
```json
{
  "version": "1.0",
  "subjects": [
    {
      "entity": "Elon Musk",
      "type": "PERSON",
      "entity_id": 8001,
      "role_description": "CEO of Tesla, Inc."
    },
    {
      "entity": "Tesla, Inc.",
      "type": "ORG",
      "entity_id": 8002
    }
  ],
  "objects": [
    {
      "entity": "Tesla stock (TSLA)",
      "type": "SECURITY",
      "entity_id": 8003
    },
    {
      "entity": "Texas manufacturing facility",
      "type": "FACILITY",
      "entity_id": 8004
    }
  ],
  "action": {
    "verb": "announce",
    "description": "announced plans for new battery manufacturing facility",
    "tense": "past"
  },
  "effect": {
    "description": "stock price increased in after-hours trading",
    "impact_level": "moderate",
    "affected_entities": [
      {
        "entity": "Tesla shareholders",
        "type": "GROUP"
      }
    ]
  },
  "datetime": {
    "extracted": "2025-10-25T16:30:00Z",
    "precision": "minute",
    "is_estimate": false
  },
  "location": {
    "place": "Texas",
    "country": "United States"
  },
  "claims": [
    {
      "claim": "Stock price increased 4.2% to $245.80",
      "verifiable": true,
      "source": "market data",
      "confidence": "high"
    },
    {
      "claim": "New factory will produce EV batteries",
      "verifiable": true,
      "source": "company announcement",
      "confidence": "high"
    },
    {
      "claim": "Production to begin Q3 2026",
      "verifiable": true,
      "source": "company announcement",
      "confidence": "high"
    }
  ],
  "quotes": [],
  "context": {
    "background": "Tesla's ongoing expansion of manufacturing capacity",
    "related_events": []
  }
}
```

**Bias Analysis:**
```json
{
  "original_bias_score": 0.86,
  "clickbait_score": 0.89,
  "removed_phrases": [
    "SOARS",
    "Brilliant Move",
    "Stuns",
    "did it again",
    "visionary",
    "genius",
    "skyrocketing",
    "greatest entrepreneur of our generation",
    "left speechless",
    "could moon"
  ],
  "bias_types_detected": [
    "personality_cult",
    "financial_hype",
    "selective_framing",
    "exaggeration",
    "opinion_as_fact"
  ],
  "quantitative_corrections": [
    {
      "original": "SOARS / skyrocketing",
      "corrected": "4.2% increase",
      "note": "Replaced hyperbole with actual percentage"
    }
  ]
}
```

---

## API Usage Examples

### Example: Normalize an article

```bash
curl -X POST "http://localhost:8000/api/news/12345/normalize" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude"
  }'
```

**Response:**
```json
{
  "news_id": 12345,
  "status": "processing",
  "job_id": "norm-12345-abc123",
  "estimated_completion": "2025-10-25T12:05:00Z"
}
```

### Example: Get normalized version

```bash
curl -X GET "http://localhost:8000/api/news/12345/normalized"
```

**Response:**
```json
{
  "id": 678,
  "news_id": 12345,
  "normalized_title": "Apple announces iPhone 16 Pro with new camera sensor technology",
  "normalized_summary": "Apple Inc. released the iPhone 16 Pro...",
  "frontmatter": { /* full JSON */ },
  "original_bias_score": 0.89,
  "clickbait_score": 0.95,
  "removed_phrases": ["MIND-BLOWING", "GAME-CHANGING", ...],
  "confidence_score": 0.91,
  "llm_model": "claude-3-5-sonnet-20241022",
  "processing_version": "1.0.0",
  "created_at": "2025-10-25T12:00:00Z"
}
```

### Example: Find all news about an entity

```bash
curl -X GET "http://localhost:8000/api/entities/search?q=Microsoft&type=ORG"
```

**Response:**
```json
[
  {
    "id": 1001,
    "name": "Microsoft",
    "type": "ORG",
    "canonical_name": "Microsoft Corporation",
    "aliases": ["MSFT", "Microsoft Corp"],
    "article_count": 245
  }
]
```

```bash
curl -X GET "http://localhost:8000/api/entities/1001/news?role=SUBJECT&limit=10"
```

**Response:**
```json
{
  "entity": {
    "id": 1001,
    "name": "Microsoft Corporation"
  },
  "articles": [
    {
      "news_id": 12345,
      "normalized_title": "Microsoft announces quarterly earnings",
      "role": "SUBJECT",
      "sentiment": "neutral",
      "date": "2025-10-25"
    }
  ],
  "total": 245
}
```

### Example: Compare sources for an event

```bash
curl -X POST "http://localhost:8000/api/events/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 7001
  }'
```

**Response:** (See "Source Comparison" in Example 3 above)

---

## Visualization Examples

### Timeline View

```
Event: Natural gas explosion at 123 Main Street
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

09:45 AM  ●  Explosion occurs (Source: StateWire)

09:52 AM  ●  First media report (Breaking24News)
          |  "BREAKING: Massive Explosion..."
          |  Bias: 0.78, Clickbait: 0.91

10:15 AM  ●  Fire Dept confirms 3 injuries (LocalNews)
          |  "Gas Line Rupture Causes Explosion..."
          |  Bias: 0.15, Clickbait: 0.22

10:30 AM  ●  Official statement (StateWire)
          |  "Downtown Building Evacuated..."
          |  Bias: 0.08, Clickbait: 0.12

11:00 AM  ●  Event normalized
          |  Canonical: "Natural gas line rupture..."
          |  Consensus established

Recommended source: LocalNewsNetwork.com (most accurate)
```

### Entity Network

```
              ┌─────────────┐
              │  Microsoft  │
              │   (ORG)     │
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    [SUBJECT]   [SUBJECT]   [OBJECT]
         │           │           │
    ┌────▼────┐ ┌───▼────┐ ┌────▼─────┐
    │Earnings │ │  Deal  │ │ Antitrust│
    │ Report  │ │  with  │ │ Lawsuit  │
    └─────────┘ │ OpenAI │ └──────────┘
                └────┬───┘
                     │
                [OBJECT]
                     │
                ┌────▼────┐
                │ OpenAI  │
                │  (ORG)  │
                └─────────┘
```

---

## Benefits Summary

### For Readers

1. **Objectivity**: Facts without editorial spin
2. **Clarity**: Clear, concise headlines
3. **Comparability**: See how sources differ
4. **Efficiency**: Get facts faster
5. **Trust**: Transparent normalization process

### For Researchers

1. **Structured Data**: Machine-readable facts
2. **Entity Tracking**: Follow entities across sources
3. **Event Timelines**: Understand chronology
4. **Source Analysis**: Evaluate bias patterns
5. **Fact Extraction**: Build knowledge graphs

### For Journalists

1. **Fact Checking**: Verify claims across sources
2. **Source Discovery**: Find diverse perspectives
3. **Bias Detection**: Identify framing differences
4. **Research Tool**: Track entities and events
5. **Story Ideas**: Discover under-reported facts

---

This normalization approach transforms EmBird from a simple aggregator into an **intelligent fact extraction and bias analysis platform**, enabling truly informed news consumption.
