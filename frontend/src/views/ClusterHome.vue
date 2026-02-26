<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const clusters = ref({})
const loading = ref(true)
const error = ref(null)
const expandedClusters = ref(new Set())

const fetchClusters = async () => {
  try {
    loading.value = true
    error.value = null
    const response = await fetch('/api/news/clusters')
    if (!response.ok) throw new Error('Failed to fetch clusters')
    clusters.value = await response.json()
  } catch (err) {
    error.value = err.message
    console.error('Error fetching clusters:', err)
  } finally {
    loading.value = false
  }
}

// Flatten subclusters to top-level display items with parent tags
const rankedTopics = computed(() => {
  const topics = []

  for (const [clusterId, cluster] of Object.entries(clusters.value)) {
    const parentKeywords = cluster.name || `Cluster ${clusterId}`

    if (cluster.subclusters && cluster.subclusters.length > 1) {
      // Promote each subcluster to a top-level topic
      for (const sub of cluster.subclusters) {
        topics.push({
          id: `${clusterId}-${sub.name}`,
          name: sub.name,
          parentName: parentKeywords,
          articles: sub.articles || [],
          subclusters: sub.subclusters || null,
          score: computeScore(sub.articles || [])
        })
      }
    } else {
      // No subclusters — show the cluster itself
      topics.push({
        id: clusterId,
        name: cluster.name || `Cluster ${clusterId}`,
        parentName: null,
        articles: cluster.articles || [],
        subclusters: null,
        score: computeScore(cluster.articles || [])
      })
    }
  }

  // Sort by score descending
  topics.sort((a, b) => b.score - a.score)
  return topics
})

// Scoring: more articles = more relevant, more hits = more important, age decays
function computeScore(articles) {
  if (!articles || articles.length === 0) return 0

  const now = Date.now()
  const articleCount = articles.length

  let totalHits = 0
  let newestMs = 0
  let oldestMs = Infinity

  for (const a of articles) {
    totalHits += a.hit_count || 1
    const firstSeen = new Date(a.first_seen_at).getTime()
    const lastSeen = new Date(a.last_seen_at).getTime()
    if (lastSeen > newestMs) newestMs = lastSeen
    if (firstSeen < oldestMs) oldestMs = firstSeen
  }

  // Relevance span in hours (how long the topic has been active)
  const spanHours = Math.max((newestMs - oldestMs) / 3600000, 0.1)
  // Age: hours since newest article
  const ageHours = Math.max((now - newestMs) / 3600000, 0)

  // Score formula:
  // - article count (weight: 10) — more coverage = more relevant
  // - total hits (weight: 2) — cross-source validation
  // - span bonus (weight: 1.5) — sustained relevance
  // - age decay (exponential half-life of 12 hours)
  const decayFactor = Math.pow(0.5, ageHours / 12)
  const rawScore = (articleCount * 10) + (totalHits * 2) + (spanHours * 1.5)

  return rawScore * decayFactor
}

const formatRelativeTime = (dateString) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const sourceDomain = (sourceUrl) => {
  try {
    return new URL(sourceUrl).hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
}

const getNewestArticle = (articles) => {
  if (!articles || articles.length === 0) return null
  return articles.reduce((newest, article) => {
    return new Date(article.last_seen_at) > new Date(newest.last_seen_at) ? article : newest
  }, articles[0])
}

const getAllTags = (topic) => {
  const tags = []
  const seen = new Set()
  const addTags = (nameStr) => {
    if (!nameStr) return
    for (const t of nameStr.split(',')) {
      const trimmed = t.trim().toLowerCase()
      if (trimmed && !seen.has(trimmed)) {
        seen.add(trimmed)
        tags.push(trimmed)
      }
    }
  }
  addTags(topic.parentName)
  addTags(topic.name)
  return tags
}

const sortedArticles = (articles) => {
  if (!articles || articles.length === 0) return []
  return [...articles].sort((a, b) => new Date(b.first_seen_at) - new Date(a.first_seen_at))
}

const toggleCluster = (topicId) => {
  if (expandedClusters.value.has(topicId)) {
    expandedClusters.value.delete(topicId)
  } else {
    expandedClusters.value.add(topicId)
  }
  expandedClusters.value = new Set(expandedClusters.value)
}

const isExpanded = (topicId) => expandedClusters.value.has(topicId)

const goToArticle = (id, event) => {
  event.stopPropagation()
  router.push(`/news/${id}`)
}

const formatScore = (score) => {
  if (score >= 100) return Math.round(score)
  return score.toFixed(1)
}

onMounted(() => {
  fetchClusters()
})
</script>

<template>
  <div class="container">
    <div class="home-header">
      <h1>Top Stories</h1>
      <p class="text-muted">Ranked by relevance, coverage, and recency</p>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading stories...</p>
    </div>

    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <div v-else class="topics-list">
      <div v-if="rankedTopics.length === 0" class="empty-state">
        <p class="text-muted">No stories available.</p>
      </div>

      <div
        v-for="(topic, rank) in rankedTopics"
        :key="topic.id"
        class="topic"
        :class="{ 'topic-expanded': isExpanded(topic.id) }"
      >
        <div class="topic-card" @click="toggleCluster(topic.id)">
          <div class="topic-rank">#{{ rank + 1 }}</div>
          <div class="topic-main">
            <div class="topic-header">
              <h2 v-if="getNewestArticle(topic.articles)" class="topic-name">{{ getNewestArticle(topic.articles).title }}</h2>
              <h2 v-else class="topic-name">{{ topic.name }}</h2>
              <div class="expand-icon" :class="{ 'expanded': isExpanded(topic.id) }">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
            </div>
            <div class="topic-tags">
              <span v-for="tag in getAllTags(topic)" :key="tag" class="tag tag-keyword">{{ tag }}</span>
              <span class="tag tag-count">{{ topic.articles.length }} article{{ topic.articles.length !== 1 ? 's' : '' }}</span>
              <span class="tag tag-score">score {{ formatScore(topic.score) }}</span>
              <span v-if="getNewestArticle(topic.articles)" class="topic-time text-muted">
                {{ formatRelativeTime(getNewestArticle(topic.articles).last_seen_at) }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="isExpanded(topic.id)" class="topic-articles">
          <div
            v-for="item in sortedArticles(topic.articles)"
            :key="item.id"
            class="article-row"
            @click="goToArticle(item.id, $event)"
          >
            <div class="article-badges">
              <span class="badge">{{ sourceDomain(item.source_url) }}</span>
              <span class="badge badge-secondary">{{ item.hit_count }} hit{{ item.hit_count !== 1 ? 's' : '' }}</span>
            </div>
            <h3 class="article-title">{{ item.title }}</h3>
            <p v-if="item.summary" class="article-summary">{{ item.summary }}</p>
            <span class="text-muted article-time">{{ formatRelativeTime(item.first_seen_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-header {
  margin-bottom: 2rem;
}

.home-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  color: var(--text-color);
}

.loading-container,
.empty-state {
  text-align: center;
  padding: 3rem 0;
}

.topics-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.topic {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: box-shadow 0.2s ease;
}

.topic:hover {
  box-shadow: var(--shadow), 0 4px 12px rgba(0, 0, 0, 0.08);
}

.topic-expanded {
  border-color: var(--primary-color);
}

.topic-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.25rem;
  cursor: pointer;
  user-select: none;
}

.topic-rank {
  flex-shrink: 0;
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--primary-color);
  opacity: 0.6;
  min-width: 2rem;
  padding-top: 0.125rem;
}

.topic-main {
  flex: 1;
  min-width: 0;
}

.topic-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.topic-name {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-color);
  line-height: 1.3;
  margin-bottom: 0.5rem;
}

.expand-icon {
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform 0.2s ease;
  margin-top: 0.125rem;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.topic-tags {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.625rem;
}

.tag {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 600;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.tag-keyword {
  background: rgba(79, 70, 229, 0.08);
  color: var(--primary-color);
}

.tag-count {
  background: var(--primary-color);
  color: white;
}

.tag-score {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-muted);
}

[data-theme="dark"] .tag-score {
  background: rgba(255, 255, 255, 0.08);
}

.topic-time {
  font-size: 0.8125rem;
}

.topic-articles {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
  background: var(--bg-color);
}

.article-row {
  padding: 1rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.article-row:hover {
  border-color: var(--primary-color);
  transform: translateX(4px);
  box-shadow: var(--shadow);
}

.article-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.article-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
  color: var(--text-color);
  line-height: 1.4;
}

.article-summary {
  color: var(--text-muted);
  margin-bottom: 0.375rem;
  font-size: 0.875rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.article-time {
  font-size: 0.8125rem;
}

@media (max-width: 768px) {
  .home-header h1 {
    font-size: 1.5rem;
  }

  .topic-card {
    padding: 1rem;
    gap: 0.75rem;
  }

  .topic-rank {
    font-size: 1rem;
    min-width: 1.75rem;
  }

  .topic-name {
    font-size: 1rem;
  }

  .topic-articles {
    padding: 0 1rem 1rem;
  }

  .article-row {
    padding: 0.875rem;
  }

  .article-title {
    font-size: 0.9375rem;
  }
}
</style>
