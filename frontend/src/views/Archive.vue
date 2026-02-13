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

// Search state
const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searched = ref(false)

const mode = ref('browse') // 'browse' or 'search'

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

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    // If search cleared, go back to browse mode
    mode.value = 'browse'
    searched.value = false
    searchResults.value = []
    return
  }

  try {
    searchLoading.value = true
    error.value = null
    searched.value = true
    mode.value = 'search'

    const params = new URLSearchParams()
    params.append('query', searchQuery.value.trim())
    params.append('limit', '20')
    if (sourceFilter.value) {
      params.append('source_url', sourceFilter.value)
    }

    const response = await fetch(`/api/news/search?${params}`)
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Search failed')
    }

    searchResults.value = await response.json()
  } catch (err) {
    error.value = err.message
    console.error('Search error:', err)
  } finally {
    searchLoading.value = false
  }
}

const handleKeypress = (event) => {
  if (event.key === 'Enter') {
    performSearch()
  }
}

const clearSearch = () => {
  searchQuery.value = ''
  searched.value = false
  searchResults.value = []
  mode.value = 'browse'
  error.value = null
}

const filterBySource = (source) => {
  if (sourceFilter.value === source) {
    sourceFilter.value = ''
    router.push({ name: 'newnews' })
  } else {
    sourceFilter.value = source
    router.push({ name: 'newnews', query: { source_url: source } })
  }
}

const getDomain = (urlString) => {
  try {
    const url = new URL(urlString)
    return url.hostname.replace('www.', '')
  } catch {
    return urlString
  }
}

const displayedItems = ref([])
watch([mode, news, searchResults], () => {
  displayedItems.value = mode.value === 'search' ? searchResults.value : news.value
}, { immediate: true })

onMounted(() => {
  sourceFilter.value = route.query.source_url || ''
  fetchSources()
  fetchNews()
})

watch(() => route.query.source_url, (newSource, oldSource) => {
  if (oldSource !== undefined) {
    sourceFilter.value = newSource || ''
    if (mode.value === 'browse') {
      fetchNews()
    } else {
      performSearch()
    }
  }
})
</script>

<template>
  <div class="container">
    <div class="archive-header">
      <h1>Archive</h1>
      <p class="text-muted">Browse, filter, and search all news articles</p>
    </div>

    <!-- Search box -->
    <div class="search-box">
      <div class="search-input-wrapper">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon-inline">
          <circle cx="11" cy="11" r="8"></circle>
          <path d="m21 21-4.35-4.35"></path>
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Semantic search across all articles..."
          @keypress="handleKeypress"
          class="search-input"
        />
      </div>
      <button
        @click="performSearch"
        :disabled="searchLoading || !searchQuery.trim()"
        class="btn btn-primary"
      >
        {{ searchLoading ? 'Searching...' : 'Search' }}
      </button>
      <button
        v-if="searched"
        @click="clearSearch"
        class="btn btn-outline"
      >
        Clear
      </button>
    </div>

    <!-- Source filter -->
    <div v-if="sources.length > 0" class="source-filter">
      <div class="source-filter-header">
        <h3>Filter by Source</h3>
        <span v-if="sourceFilter" class="active-filter-label">
          Active: {{ getDomain(sourceFilter) }}
        </span>
      </div>
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

    <!-- Mode indicator -->
    <div class="results-info">
      <template v-if="mode === 'search' && searched">
        <p class="text-muted">
          Found {{ searchResults.length }} result{{ searchResults.length !== 1 ? 's' : '' }}
          for "<strong>{{ searchQuery }}</strong>"
          <span v-if="sourceFilter"> from {{ getDomain(sourceFilter) }}</span>
        </p>
      </template>
      <template v-else-if="!loading">
        <p class="text-muted">
          Showing {{ news.length }} article{{ news.length !== 1 ? 's' : '' }}
          <span v-if="sourceFilter"> from {{ getDomain(sourceFilter) }}</span>
        </p>
      </template>
    </div>

    <!-- Loading state -->
    <div v-if="loading || searchLoading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">{{ searchLoading ? 'Searching...' : 'Loading articles...' }}</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Results list -->
    <div v-else class="news-list">
      <div v-if="displayedItems.length === 0" class="empty-state">
        <p class="text-muted" v-if="mode === 'search'">No matching articles found. Try a different search term.</p>
        <p class="text-muted" v-else>No news articles found.</p>
      </div>
      <NewsCard
        v-for="item in displayedItems"
        :key="item.id"
        :news-item="item"
        :show-similarity="mode === 'search'"
      />
    </div>
  </div>
</template>

<style scoped>
.archive-header {
  margin-bottom: 2rem;
}

.archive-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  color: var(--text-color);
}

.search-box {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  align-items: stretch;
}

.search-input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon-inline {
  position: absolute;
  left: 0.875rem;
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.75rem 1rem 0.75rem 2.75rem;
  font-size: 1rem;
  border: 2px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
  color: var(--text-color);
  transition: border-color 0.2s ease;
}

.search-input:focus {
  border-color: var(--primary-color);
  outline: none;
}

.search-box .btn {
  padding: 0.75rem 1.5rem;
  white-space: nowrap;
}

.search-box .btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.source-filter {
  margin-bottom: 1.5rem;
  padding: 1.25rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.source-filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.source-filter h3 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.active-filter-label {
  font-size: 0.8125rem;
  color: var(--primary-color);
  font-weight: 500;
}

.source-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.source-tag {
  padding: 0.375rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-color);
  font-size: 0.8125rem;
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

.results-info {
  margin-bottom: 1rem;
}

.results-info strong {
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

.news-list {
  margin-top: 0.5rem;
}

@media (max-width: 768px) {
  .archive-header h1 {
    font-size: 1.5rem;
  }

  .search-box {
    flex-direction: column;
  }

  .search-box .btn {
    width: 100%;
  }

  .source-filter {
    padding: 1rem;
  }

  .source-filter-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
  }
}
</style>
