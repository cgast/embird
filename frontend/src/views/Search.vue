<script setup>
import { ref, onMounted } from 'vue'
import NewsCard from '../components/NewsCard.vue'

const searchQuery = ref('')
const searchResults = ref([])
const loading = ref(false)
const error = ref(null)
const searched = ref(false)
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

const getDomain = (urlString) => {
  try {
    const url = new URL(urlString)
    return url.hostname.replace('www.', '')
  } catch {
    return urlString
  }
}

const performSearch = async () => {
  if (!searchQuery.value.trim()) {
    error.value = 'Please enter a search query'
    return
  }

  try {
    loading.value = true
    error.value = null
    searched.value = true

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
    loading.value = false
  }
}

const handleKeypress = (event) => {
  if (event.key === 'Enter') {
    performSearch()
  }
}

onMounted(() => {
  fetchSources()
})
</script>

<template>
  <div class="container">
    <div class="search-header">
      <h1>Semantic Search</h1>
      <p class="text-muted">Search news articles by meaning, not just keywords</p>
    </div>

    <!-- Search box -->
    <div class="search-box">
      <input
        v-model="searchQuery"
        type="search"
        placeholder="Search for news articles..."
        @keypress="handleKeypress"
        class="search-input"
      />
      <button
        @click="performSearch"
        :disabled="loading || !searchQuery.trim()"
        class="btn btn-primary"
      >
        {{ loading ? 'Searching...' : 'Search' }}
      </button>
    </div>

    <!-- Source filter -->
    <div v-if="sources.length > 0" class="source-filter">
      <h3>Filter by Source</h3>
      <div class="source-tags">
        <button
          :class="['source-tag', { active: sourceFilter === '' }]"
          @click="sourceFilter = ''"
        >
          All Sources
        </button>
        <button
          v-for="source in sources"
          :key="source"
          :class="['source-tag', { active: sourceFilter === source }]"
          @click="sourceFilter = source"
        >
          {{ getDomain(source) }}
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Searching...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Search results -->
    <div v-else-if="searched" class="search-results">
      <div class="results-header">
        <h2>Search Results</h2>
        <p class="text-muted">Found {{ searchResults.length }} result{{ searchResults.length !== 1 ? 's' : '' }} for "{{ searchQuery }}"</p>
      </div>

      <div v-if="searchResults.length === 0" class="empty-state">
        <p class="text-muted">No matching articles found. Try a different search term.</p>
      </div>

      <NewsCard
        v-for="item in searchResults"
        :key="item.id"
        :news-item="item"
        :show-similarity="true"
      />
    </div>

    <!-- Initial state -->
    <div v-else class="initial-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="search-icon">
        <circle cx="11" cy="11" r="8"></circle>
        <path d="m21 21-4.35-4.35"></path>
      </svg>
      <p class="text-muted">Enter a search query to find relevant news articles</p>
    </div>
  </div>
</template>

<style scoped>
.search-header {
  margin-bottom: 2rem;
  text-align: center;
}

.search-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.search-box {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}

.search-input {
  flex: 1;
  padding: 0.75rem 1rem;
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
  padding: 0.75rem 2rem;
  white-space: nowrap;
}

.search-box .btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.source-filter {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
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

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.results-header {
  margin-bottom: 2rem;
}

.results-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
}

.initial-state {
  text-align: center;
  padding: 4rem 0;
}

.search-icon {
  color: var(--text-muted);
  margin-bottom: 1rem;
}

@media (max-width: 768px) {
  .search-header h1 {
    font-size: 1.5rem;
  }

  .search-box {
    flex-direction: column;
  }

  .search-box .btn {
    width: 100%;
  }
}
</style>
