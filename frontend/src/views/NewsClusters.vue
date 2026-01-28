<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const clusters = ref({})
const loading = ref(true)
const error = ref(null)

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

const sourceDomain = (sourceUrl) => {
  try {
    const url = new URL(sourceUrl)
    return url.hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
}

const goToArticle = (id) => {
  router.push(`/news/${id}`)
}

const clusterKeys = ref([])

onMounted(async () => {
  await fetchClusters()
  clusterKeys.value = Object.keys(clusters.value).sort((a, b) => b - a)
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
      >
        <div class="cluster-header">
          <h2>Cluster {{ clusterId }}</h2>
          <span class="badge">{{ clusters[clusterId].length }} article{{ clusters[clusterId].length !== 1 ? 's' : '' }}</span>
        </div>

        <div class="cluster-items">
          <div
            v-for="item in clusters[clusterId]"
            :key="item.id"
            class="cluster-item"
            @click="goToArticle(item.id)"
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
            <p class="text-muted item-date">{{ formatDate(item.first_seen_at) }}</p>
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
  padding: 1.5rem;
  margin-bottom: 2rem;
  box-shadow: var(--shadow);
}

.cluster-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.cluster-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--primary-color);
}

.cluster-items {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cluster-item {
  padding: 1.25rem;
  background: var(--bg-color);
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
  margin-bottom: 0.75rem;
}

.item-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-color);
  line-height: 1.4;
}

.item-summary {
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  font-size: 0.9375rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-date {
  font-size: 0.875rem;
}

@media (max-width: 768px) {
  .clusters-header h1 {
    font-size: 1.5rem;
  }

  .cluster {
    padding: 1rem;
  }

  .cluster-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .cluster-header h2 {
    font-size: 1.25rem;
  }

  .cluster-item {
    padding: 1rem;
  }

  .item-title {
    font-size: 1rem;
  }
}
</style>
