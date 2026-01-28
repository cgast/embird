<script setup>
import { ref, onMounted } from 'vue'

const sources = ref([])
const loading = ref(true)
const error = ref(null)
const showAddForm = ref(false)

const newSource = ref({
  url: ''
})

const fetchSources = async () => {
  try {
    loading.value = true
    error.value = null

    const response = await fetch('/api/urls')
    if (!response.ok) throw new Error('Failed to fetch sources')

    sources.value = await response.json()

  } catch (err) {
    error.value = err.message
    console.error('Error fetching sources:', err)
  } finally {
    loading.value = false
  }
}

const addSource = async () => {
  if (!newSource.value.url) {
    error.value = 'URL is required'
    return
  }

  try {
    const response = await fetch('/api/urls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSource.value)
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to add source')
    }

    newSource.value = { url: '' }
    showAddForm.value = false
    await fetchSources()

  } catch (err) {
    error.value = err.message
  }
}

const deleteSource = async (id) => {
  if (!confirm('Are you sure you want to delete this source?')) return

  try {
    const response = await fetch(`/api/urls/${id}`, {
      method: 'DELETE'
    })

    if (!response.ok) throw new Error('Failed to delete source')

    await fetchSources()

  } catch (err) {
    error.value = err.message
  }
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

const getDomain = (url) => {
  try {
    const urlObj = new URL(url)
    return urlObj.hostname.replace('www.', '')
  } catch {
    return url
  }
}

onMounted(() => {
  fetchSources()
})
</script>

<template>
  <div class="container">
    <div class="sources-header">
      <h1>News Sources</h1>
      <p class="text-muted">Manage RSS feed URLs for news aggregation</p>
    </div>

    <!-- Error alert -->
    <div v-if="error" class="alert mb-3">
      <strong>Error:</strong> {{ error }}
      <button @click="error = null" class="btn btn-sm btn-outline" style="float: right;">Dismiss</button>
    </div>

    <!-- Add new source -->
    <div class="card mb-4">
      <div class="card-header">
        <h2>Add New Source</h2>
        <button v-if="!showAddForm" @click="showAddForm = true" class="btn btn-primary">
          + Add Source
        </button>
      </div>
      <div v-if="showAddForm" class="card-body">
        <form @submit.prevent="addSource">
          <div class="form-group mb-3">
            <label>RSS Feed URL</label>
            <input v-model="newSource.url" type="url"
                   placeholder="https://example.com/feed.xml" required />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Add Source</button>
            <button type="button" @click="showAddForm = false; newSource = { url: '' }"
                    class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading sources...</p>
    </div>

    <!-- Sources list -->
    <div v-else-if="sources.length > 0" class="sources-list">
      <div class="card">
        <div class="card-header">
          <h2>Existing Sources</h2>
          <span class="badge">{{ sources.length }} source{{ sources.length !== 1 ? 's' : '' }}</span>
        </div>
        <div class="sources-grid">
          <div v-for="source in sources" :key="source.id" class="source-item">
            <div class="source-content">
              <h3>{{ getDomain(source.url) }}</h3>
              <a :href="source.url" target="_blank" rel="noopener noreferrer" class="source-url">
                {{ source.url }}
              </a>
              <p class="text-muted source-date">Added: {{ formatDate(source.created_at) }}</p>
            </div>
            <div class="source-actions">
              <button @click="deleteSource(source.id)" class="btn btn-sm btn-outline">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="rss-icon">
        <path d="M4 11a9 9 0 0 1 9 9"></path>
        <path d="M4 4a16 16 0 0 1 16 16"></path>
        <circle cx="5" cy="19" r="1"></circle>
      </svg>
      <p class="text-muted">No sources configured. Add your first RSS feed above.</p>
    </div>
  </div>
</template>

<style scoped>
.sources-header {
  margin-bottom: 2rem;
}

.sources-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.card-body {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-color);
}

.form-actions {
  display: flex;
  gap: 1rem;
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.empty-state {
  text-align: center;
  padding: 4rem 0;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.rss-icon {
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.sources-grid {
  display: flex;
  flex-direction: column;
}

.source-item {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  transition: background-color 0.2s ease;
}

.source-item:hover {
  background-color: var(--bg-color);
}

.source-item:last-child {
  border-bottom: none;
}

.source-content {
  flex: 1;
}

.source-content h3 {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.source-url {
  display: block;
  color: var(--primary-color);
  text-decoration: none;
  margin-bottom: 0.5rem;
  word-break: break-all;
}

.source-url:hover {
  text-decoration: underline;
}

.source-date {
  font-size: 0.875rem;
}

.source-actions {
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .sources-header h1 {
    font-size: 1.5rem;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .source-item {
    flex-direction: column;
  }

  .source-actions {
    width: 100%;
  }

  .source-actions .btn {
    width: 100%;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions .btn {
    width: 100%;
  }
}
</style>
