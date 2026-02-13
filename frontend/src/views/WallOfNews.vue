<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const clusters = ref({})
const allNews = ref([])
const loading = ref(true)
const error = ref(null)

// Fetch clusters (for scoring context) and all recent news in parallel
const fetchData = async () => {
  try {
    loading.value = true
    error.value = null

    const [clustersRes, newsRes] = await Promise.all([
      fetch('/api/news/clusters'),
      fetch('/api/news?limit=500')
    ])

    if (!clustersRes.ok) throw new Error('Failed to fetch clusters')
    if (!newsRes.ok) throw new Error('Failed to fetch news')

    clusters.value = await clustersRes.json()
    allNews.value = await newsRes.json()
  } catch (err) {
    error.value = err.message
    console.error('Error fetching wall data:', err)
  } finally {
    loading.value = false
  }
}

// Build a map of article id -> cluster score for highlighting
const articleScores = computed(() => {
  const scores = new Map()

  for (const [clusterId, cluster] of Object.entries(clusters.value)) {
    if (cluster.subclusters && cluster.subclusters.length > 1) {
      for (const sub of cluster.subclusters) {
        const score = computeScore(sub.articles || [])
        for (const a of (sub.articles || [])) {
          const existing = scores.get(a.id) || 0
          if (score > existing) scores.set(a.id, score)
        }
      }
    } else {
      const score = computeScore(cluster.articles || [])
      for (const a of (cluster.articles || [])) {
        const existing = scores.get(a.id) || 0
        if (score > existing) scores.set(a.id, score)
      }
    }
  }

  return scores
})

// Same scoring algorithm as ClusterHome
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

  const spanHours = Math.max((newestMs - oldestMs) / 3600000, 0.1)
  const ageHours = Math.max((now - newestMs) / 3600000, 0)
  const decayFactor = Math.pow(0.5, ageHours / 12)
  const rawScore = (articleCount * 10) + (totalHits * 2) + (spanHours * 1.5)

  return rawScore * decayFactor
}

// Score thresholds for highlighting tiers
const scoreThresholds = computed(() => {
  const allScores = [...articleScores.value.values()].filter(s => s > 0)
  if (allScores.length === 0) return { hot: 100, warm: 50 }
  allScores.sort((a, b) => b - a)
  return {
    hot: allScores[Math.floor(allScores.length * 0.1)] || 0,  // top 10%
    warm: allScores[Math.floor(allScores.length * 0.3)] || 0   // top 30%
  }
})

// Build cluster sections: group articles by their cluster topic
const clusterSections = computed(() => {
  const sections = []

  for (const [clusterId, cluster] of Object.entries(clusters.value)) {
    if (cluster.subclusters && cluster.subclusters.length > 1) {
      for (const sub of cluster.subclusters) {
        const arts = (sub.articles || []).slice()
        if (arts.length === 0) continue
        arts.sort((a, b) => new Date(b.last_seen_at) - new Date(a.last_seen_at))
        const score = computeScore(arts)
        sections.push({
          id: `${clusterId}-${sub.name}`,
          name: sub.name,
          articles: arts,
          score
        })
      }
    } else {
      const arts = (cluster.articles || []).slice()
      if (arts.length === 0) continue
      arts.sort((a, b) => new Date(b.last_seen_at) - new Date(a.last_seen_at))
      const score = computeScore(arts)
      sections.push({
        id: clusterId,
        name: cluster.name || `Cluster ${clusterId}`,
        articles: arts,
        score
      })
    }
  }

  sections.sort((a, b) => b.score - a.score)
  return sections
})

// Group remaining articles (not in clusters) by source domain
const sourceSections = computed(() => {
  const clusteredIds = new Set()
  for (const section of clusterSections.value) {
    for (const a of section.articles) {
      clusteredIds.add(a.id)
    }
  }

  const bySource = new Map()
  for (const article of allNews.value) {
    if (clusteredIds.has(article.id)) continue
    const domain = sourceDomain(article.source_url)
    if (!bySource.has(domain)) {
      bySource.set(domain, { name: domain, articles: [], sourceUrl: article.source_url })
    }
    bySource.get(domain).articles.push(article)
  }

  const sections = [...bySource.values()]
  sections.sort((a, b) => b.articles.length - a.articles.length)
  return sections
})

const totalHeadlines = computed(() => {
  let count = 0
  for (const s of clusterSections.value) count += s.articles.length
  for (const s of sourceSections.value) count += s.articles.length
  return count
})

const getHeatClass = (articleId) => {
  const score = articleScores.value.get(articleId) || 0
  if (score >= scoreThresholds.value.hot) return 'heat-hot'
  if (score >= scoreThresholds.value.warm) return 'heat-warm'
  return ''
}

const sourceDomain = (sourceUrl) => {
  try {
    return new URL(sourceUrl).hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
}

const formatRelativeTime = (dateString) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return 'now'
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  if (diffDays < 7) return `${diffDays}d`
  return date.toLocaleDateString()
}

const goToArticle = (id) => {
  router.push(`/news/${id}`)
}

const openExternal = (url, event) => {
  event.stopPropagation()
  window.open(url, '_blank', 'noopener,noreferrer')
}

const formatScore = (score) => {
  if (score >= 100) return Math.round(score)
  return score.toFixed(1)
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="wall-container">
    <div class="wall-header">
      <div class="wall-title-row">
        <h1>Wall of News</h1>
        <span class="wall-count" v-if="!loading">{{ totalHeadlines }} headlines</span>
      </div>
      <p class="text-muted">All stories at a glance — organized by topic and source</p>
      <div class="wall-legend">
        <span class="legend-item"><span class="legend-dot heat-hot-dot"></span> Top story</span>
        <span class="legend-item"><span class="legend-dot heat-warm-dot"></span> Trending</span>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading wall...</p>
    </div>

    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <template v-else>
      <!-- Cluster-based sections -->
      <div v-if="clusterSections.length > 0" class="wall-section">
        <h2 class="wall-section-title">Topics</h2>
        <div class="wall-grid">
          <div
            v-for="section in clusterSections"
            :key="section.id"
            class="wall-column"
          >
            <div class="column-header">
              <span class="column-name">{{ section.name }}</span>
              <span class="column-meta">{{ section.articles.length }} · {{ formatScore(section.score) }}</span>
            </div>
            <ul class="headline-list">
              <li
                v-for="article in section.articles"
                :key="article.id"
                class="headline-item"
                :class="getHeatClass(article.id)"
                @click="goToArticle(article.id)"
              >
                <span class="headline-time">{{ formatRelativeTime(article.last_seen_at) }}</span>
                <span class="headline-title" @click.middle.prevent="openExternal(article.url, $event)">{{ article.title }}</span>
                <span class="headline-source">{{ sourceDomain(article.source_url) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Source-based sections for unclustered articles -->
      <div v-if="sourceSections.length > 0" class="wall-section">
        <h2 class="wall-section-title">By Source</h2>
        <div class="wall-grid">
          <div
            v-for="section in sourceSections"
            :key="section.name"
            class="wall-column"
          >
            <div class="column-header">
              <span class="column-name">{{ section.name }}</span>
              <span class="column-meta">{{ section.articles.length }}</span>
            </div>
            <ul class="headline-list">
              <li
                v-for="article in section.articles"
                :key="article.id"
                class="headline-item"
                :class="getHeatClass(article.id)"
                @click="goToArticle(article.id)"
              >
                <span class="headline-time">{{ formatRelativeTime(article.last_seen_at) }}</span>
                <span class="headline-title" @click.middle.prevent="openExternal(article.url, $event)">{{ article.title }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div v-if="clusterSections.length === 0 && sourceSections.length === 0" class="empty-state">
        <p class="text-muted">No news articles available.</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wall-container {
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
  padding: 0 1rem;
}

.wall-header {
  margin-bottom: 1.5rem;
  padding: 0 0.5rem;
}

.wall-title-row {
  display: flex;
  align-items: baseline;
  gap: 1rem;
}

.wall-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.wall-count {
  font-size: 0.875rem;
  color: var(--text-muted);
  font-weight: 500;
  background: var(--bg-color);
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.wall-legend {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.heat-hot-dot {
  background: #e74c3c;
}

.heat-warm-dot {
  background: #f39c12;
}

.wall-section {
  margin-bottom: 2rem;
}

.wall-section-title {
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
  padding: 0 0.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.5rem;
}

.wall-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
  align-items: start;
}

.wall-column {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
  gap: 0.5rem;
}

.column-name {
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.column-meta {
  font-size: 0.6875rem;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.headline-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.headline-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.25rem 0.5rem;
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background-color 0.15s ease;
  line-height: 1.35;
}

.headline-item:last-child {
  border-bottom: none;
}

.headline-item:hover {
  background: var(--bg-color);
}

.headline-item.heat-hot {
  border-left: 3px solid #e74c3c;
  padding-left: calc(0.75rem - 3px);
}

.headline-item.heat-hot .headline-title {
  font-weight: 700;
  color: var(--text-color);
}

.headline-item.heat-warm {
  border-left: 3px solid #f39c12;
  padding-left: calc(0.75rem - 3px);
}

.headline-item.heat-warm .headline-title {
  font-weight: 600;
}

.headline-time {
  font-size: 0.6875rem;
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 1.5rem;
}

.headline-title {
  font-size: 0.8125rem;
  color: var(--text-color);
  flex: 1;
  min-width: 0;
}

.headline-source {
  font-size: 0.6875rem;
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.7;
}

.loading-container,
.empty-state {
  text-align: center;
  padding: 3rem 0;
}

@media (min-width: 1400px) {
  .wall-grid {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}

@media (max-width: 768px) {
  .wall-container {
    padding: 0 0.5rem;
  }

  .wall-header h1 {
    font-size: 1.5rem;
  }

  .wall-grid {
    grid-template-columns: 1fr;
  }

  .headline-item {
    padding: 0.5rem 0.75rem;
  }
}
</style>
