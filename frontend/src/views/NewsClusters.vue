<script setup>
import { ref, onMounted } from 'vue'
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

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString()
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
    const url = new URL(sourceUrl)
    return url.hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
}

const goToArticle = (id, event) => {
  event.stopPropagation()
  router.push(`/news/${id}`)
}

// Get cluster name (supports both old and new API format)
const getClusterName = (clusterId) => {
  const cluster = clusters.value[clusterId]
  if (cluster && cluster.name) {
    return cluster.name
  }
  return `Cluster ${clusterId}`
}

// Get articles from cluster (supports both old and new API format)
const getClusterArticles = (clusterId) => {
  const cluster = clusters.value[clusterId]
  if (cluster && cluster.articles) {
    return cluster.articles
  }
  // Old format: cluster is directly an array of articles
  return Array.isArray(cluster) ? cluster : []
}

// Get the newest article in a cluster (by first_seen_at)
const getNewestArticle = (clusterId) => {
  const articles = getClusterArticles(clusterId)
  if (articles.length === 0) return null

  return articles.reduce((newest, article) => {
    const newestDate = new Date(newest.first_seen_at)
    const articleDate = new Date(article.first_seen_at)
    return articleDate > newestDate ? article : newest
  }, articles[0])
}

// Toggle cluster expansion
const toggleCluster = (clusterId) => {
  if (expandedClusters.value.has(clusterId)) {
    expandedClusters.value.delete(clusterId)
  } else {
    expandedClusters.value.add(clusterId)
  }
  // Trigger reactivity
  expandedClusters.value = new Set(expandedClusters.value)
}

const isExpanded = (clusterId) => {
  return expandedClusters.value.has(clusterId)
}

const clusterKeys = ref([])

onMounted(async () => {
  await fetchClusters()
  // Sort clusters by number of articles (descending)
  clusterKeys.value = Object.keys(clusters.value).sort((a, b) => {
    const aCount = getClusterArticles(a).length
    const bCount = getClusterArticles(b).length
    return bCount - aCount
  })
})
</script>

<template>
  <div class="container">
    <div class="clusters-header">
      <h1>News Clusters</h1>
      <p class="text-muted">Articles grouped by semantic similarity</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading clusters...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Clusters -->
    <div v-else class="clusters-container">
      <div v-if="clusterKeys.length === 0" class="empty-state">
        <p class="text-muted">No clusters available.</p>
      </div>

      <div
        v-for="clusterId in clusterKeys"
        :key="clusterId"
        class="cluster"
        :class="{ 'cluster-expanded': isExpanded(clusterId) }"
      >
        <div class="cluster-card" @click="toggleCluster(clusterId)">
          <div class="cluster-card-content">
            <div class="cluster-info">
              <h2 class="cluster-name">{{ getClusterName(clusterId) }}</h2>
              <div class="cluster-meta">
                <span class="badge badge-count">{{ getClusterArticles(clusterId).length }} article{{ getClusterArticles(clusterId).length !== 1 ? 's' : '' }}</span>
                <span v-if="getNewestArticle(clusterId)" class="newest-time text-muted">
                  {{ formatRelativeTime(getNewestArticle(clusterId).first_seen_at) }}
                </span>
              </div>
            </div>
            <div class="expand-icon" :class="{ 'expanded': isExpanded(clusterId) }">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </div>
          <div v-if="getNewestArticle(clusterId)" class="newest-headline">
            <span class="headline-label">Latest:</span>
            <span class="headline-text">{{ getNewestArticle(clusterId).title }}</span>
          </div>
        </div>

        <div v-if="isExpanded(clusterId)" class="cluster-items">
          <div
            v-for="item in getClusterArticles(clusterId)"
            :key="item.id"
            class="cluster-item"
            @click="goToArticle(item.id, $event)"
          >
            <div class="item-header">
              <span class="badge">{{ sourceDomain(item.source_url) }}</span>
              <span class="badge badge-secondary">{{ item.hit_count }} hits</span>
              <span v-if="item.similarity" class="badge">
                {{ Math.round(item.similarity * 100) }}% match
              </span>
            </div>
            <h3 class="item-title">{{ item.title }}</h3>
            <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
            <p class="text-muted item-date">{{ formatRelativeTime(item.first_seen_at) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.clusters-header {
  margin-bottom: 2rem;
}

.clusters-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
}

.cluster {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 1rem;
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: box-shadow 0.2s ease;
}

.cluster:hover {
  box-shadow: var(--shadow), 0 4px 12px rgba(0, 0, 0, 0.08);
}

.cluster-expanded {
  border-color: var(--primary-color);
}

.cluster-card {
  padding: 1.25rem;
  cursor: pointer;
  user-select: none;
}

.cluster-card-content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.cluster-info {
  flex: 1;
  min-width: 0;
}

.cluster-name {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 0.5rem;
  line-height: 1.3;
}

.cluster-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.badge-count {
  background: var(--primary-color);
  color: white;
}

.newest-time {
  font-size: 0.875rem;
}

.expand-icon {
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform 0.2s ease;
  margin-top: 0.25rem;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.newest-headline {
  margin-top: 0.875rem;
  padding-top: 0.875rem;
  border-top: 1px solid var(--border-color);
  font-size: 0.9375rem;
  line-height: 1.4;
  display: flex;
  gap: 0.5rem;
}

.headline-label {
  color: var(--text-muted);
  flex-shrink: 0;
  font-weight: 500;
}

.headline-text {
  color: var(--text-color);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cluster-items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0 1.25rem 1.25rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
  background: var(--bg-color);
}

.cluster-item {
  padding: 1rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cluster-item:hover {
  border-color: var(--primary-color);
  transform: translateX(4px);
  box-shadow: var(--shadow);
}

.item-header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.item-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-color);
  line-height: 1.4;
}

.item-summary {
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-date {
  font-size: 0.8125rem;
}

@media (max-width: 768px) {
  .clusters-header h1 {
    font-size: 1.5rem;
  }

  .cluster-card {
    padding: 1rem;
  }

  .cluster-name {
    font-size: 1rem;
  }

  .cluster-items {
    padding: 0 1rem 1rem;
  }

  .cluster-item {
    padding: 0.875rem;
  }

  .item-title {
    font-size: 0.9375rem;
  }

  .newest-headline {
    flex-direction: column;
    gap: 0.25rem;
  }
}
</style>
