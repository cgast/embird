<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NewsCard from '../components/NewsCard.vue'

const route = useRoute()
const router = useRouter()

const news = ref([])
const loading = ref(true)
const error = ref(null)
const sourceFilter = ref('')
const sources = ref([])

const fetchSources = async () => {
  try {
    const response = await fetch('/api/urls')
    if (!response.ok) throw new Error('Failed to fetch sources')
    const urls = await response.json()
    sources.value = urls.map(u => u.url).sort()
  } catch (err) {
    console.error('Error fetching sources:', err)
  }
}

const fetchNews = async () => {
  try {
    loading.value = true
    error.value = null

    const params = new URLSearchParams()
    if (sourceFilter.value) {
      params.append('source_url', sourceFilter.value)
    }
    params.append('limit', '100')

    const response = await fetch(`/api/news?${params}`)
    if (!response.ok) throw new Error('Failed to fetch news')

    news.value = await response.json()

  } catch (err) {
    error.value = err.message
    console.error('Error fetching news:', err)
  } finally {
    loading.value = false
  }
}

const filterBySource = (source) => {
  if (sourceFilter.value === source) {
    // Toggle off
    sourceFilter.value = ''
    router.push({ name: 'news' })
  } else {
    sourceFilter.value = source
    router.push({ name: 'news', query: { source_url: source } })
  }
}

// Helper function to extract domain from URL
const getDomain = (urlString) => {
  try {
    const url = new URL(urlString)
    return url.hostname.replace('www.', '')
  } catch {
    return urlString
  }
}

// Initialize source filter from URL on mount
onMounted(() => {
  sourceFilter.value = route.query.source_url || ''
  fetchSources()
  fetchNews()
})

// Watch for query parameter changes (after initial mount)
watch(() => route.query.source_url, (newSource, oldSource) => {
  // Only refetch if the source actually changed (not on initial mount)
  if (oldSource !== undefined) {
    sourceFilter.value = newSource || ''
    fetchNews()
  }
})
</script>

<template>
  <div class="container">
    <div class="news-header">
      <h1>All News</h1>
      <p class="text-muted">Browse all news articles from your sources</p>
    </div>

    <!-- Source filter -->
    <div v-if="sources.length > 0" class="source-filter">
      <h3>Filter by Source</h3>
      <div class="source-tags">
        <button
          v-for="source in sources"
          :key="source"
          :class="['source-tag', { active: sourceFilter === source }]"
          @click="filterBySource(source)"
        >
          {{ getDomain(source) }}
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading news...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- News list -->
    <div v-else class="news-list">
      <div class="news-count">
        <p class="text-muted">
          Showing {{ news.length }} article{{ news.length !== 1 ? 's' : '' }}
          <span v-if="sourceFilter"> from {{ getDomain(sourceFilter) }}</span>
        </p>
      </div>

      <div v-if="news.length === 0" class="empty-state">
        <p class="text-muted">No news articles found.</p>
      </div>
      <NewsCard
        v-for="item in news"
        :key="item.id"
        :news-item="item"
      />
    </div>
  </div>
</template>

<style scoped>
.news-header {
  margin-bottom: 2rem;
}

.news-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.source-filter {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.source-filter h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.source-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.source-tag {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-color);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.source-tag:hover {
  border-color: var(--primary-color);
  background: var(--surface-color);
}

.source-tag.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.news-count {
  margin-bottom: 1rem;
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
}

.news-list {
  margin-top: 1rem;
}

@media (max-width: 768px) {
  .news-header h1 {
    font-size: 1.5rem;
  }

  .source-filter {
    padding: 1rem;
  }
}
</style>
