<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const clusters = ref({})
const allNews = ref([])
const loading = ref(true)
const error = ref(null)

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
    console.error('Error fetching cluster detail:', err)
  } finally {
    loading.value = false
  }
}

// Find the matching cluster/subcluster by route param, or fall back to source grouping
const cluster = computed(() => {
  const id = route.params.id
  if (!id) return null

  // Try cluster/subcluster match first
  for (const [clusterId, c] of Object.entries(clusters.value)) {
    if (c.subclusters && c.subclusters.length > 1) {
      for (const sub of c.subclusters) {
        if (`${clusterId}-${sub.name}` === id) {
          return {
            id,
            name: sub.name,
            articles: (sub.articles || []).slice().sort(
              (a, b) => new Date(b.last_seen_at) - new Date(a.last_seen_at)
            )
          }
        }
      }
    }
    if (clusterId === id) {
      return {
        id,
        name: c.name || `Cluster ${clusterId}`,
        articles: (c.articles || []).slice().sort(
          (a, b) => new Date(b.last_seen_at) - new Date(a.last_seen_at)
        )
      }
    }
  }

  // Fall back to source domain grouping (for "By Source" sections)
  const sourceArticles = allNews.value.filter(a => sourceDomain(a.source_url) === id)
  if (sourceArticles.length > 0) {
    return {
      id,
      name: id,
      articles: sourceArticles.slice().sort(
        (a, b) => new Date(b.last_seen_at) - new Date(a.last_seen_at)
      )
    }
  }

  return null
})

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
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const goToArticle = (id) => {
  router.push(`/news/${id}`)
}

const openExternal = (url, event) => {
  event.stopPropagation()
  window.open(url, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="container">
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading cluster...</p>
    </div>

    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <div v-else-if="!cluster" class="empty-state">
      <p class="text-muted">Cluster not found.</p>
      <router-link to="/wall" class="back-link">Back to Wall of News</router-link>
    </div>

    <template v-else>
      <div class="detail-header">
        <router-link to="/wall" class="back-link">&larr; Wall of News</router-link>
        <h1>{{ cluster.name }}</h1>
        <p class="text-muted">{{ cluster.articles.length }} article{{ cluster.articles.length !== 1 ? 's' : '' }}</p>
      </div>

      <div class="articles-list">
        <div
          v-for="article in cluster.articles"
          :key="article.id"
          class="article-row"
          @click="goToArticle(article.id)"
        >
          <div class="article-meta">
            <span class="badge">{{ sourceDomain(article.source_url) }}</span>
            <span class="badge badge-secondary">{{ article.hit_count }} hit{{ article.hit_count !== 1 ? 's' : '' }}</span>
            <span class="text-muted article-time">{{ formatRelativeTime(article.last_seen_at) }}</span>
          </div>
          <h3 class="article-title" @click.middle.prevent="openExternal(article.url, $event)">{{ article.title }}</h3>
          <p v-if="article.summary" class="article-summary">{{ article.summary }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail-header {
  margin-bottom: 1.5rem;
}

.back-link {
  display: inline-block;
  font-size: 0.875rem;
  color: var(--primary-color);
  text-decoration: none;
  margin-bottom: 0.75rem;
}

.back-link:hover {
  text-decoration: underline;
}

.detail-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.article-row {
  padding: 1rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.article-row:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow);
}

.article-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.article-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-color);
  line-height: 1.4;
  margin-bottom: 0.25rem;
}

.article-summary {
  color: var(--text-muted);
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

.loading-container,
.empty-state {
  text-align: center;
  padding: 3rem 0;
}

@media (max-width: 768px) {
  .detail-header h1 {
    font-size: 1.25rem;
  }

  .article-row {
    padding: 0.875rem;
  }
}
</style>
