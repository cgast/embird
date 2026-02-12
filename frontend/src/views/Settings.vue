<script setup>
import { ref, onMounted } from 'vue'

// Tab state
const activeTab = ref('preferences')

// Login state
const isLoggedIn = ref(false)
const loginForm = ref({ username: '', password: '' })
const loginError = ref(null)
const loginLoading = ref(false)

// Preference vectors state
const vectors = ref([])
const vectorsLoading = ref(true)
const vectorsError = ref(null)
const showAddVectorForm = ref(false)
const editingVectorId = ref(null)
const newVector = ref({ title: '', description: '' })

// Sources state
const sources = ref([])
const sourcesLoading = ref(true)
const sourcesError = ref(null)
const showAddSourceForm = ref(false)
const newSource = ref({ url: '', type: 'rss' })

// Check login status on mount
const checkLogin = () => {
  const token = localStorage.getItem('embird_token')
  isLoggedIn.value = !!token
}

const handleLogin = async () => {
  if (!loginForm.value.username || !loginForm.value.password) {
    loginError.value = 'Username and password are required'
    return
  }

  try {
    loginLoading.value = true
    loginError.value = null

    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm.value)
    })

    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || 'Invalid credentials')
    }

    const data = await response.json()
    localStorage.setItem('embird_token', data.token || 'authenticated')
    isLoggedIn.value = true
    loginForm.value = { username: '', password: '' }

  } catch (err) {
    loginError.value = err.message
  } finally {
    loginLoading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('embird_token')
  isLoggedIn.value = false
}

// Preference vectors methods
const fetchVectors = async () => {
  try {
    vectorsLoading.value = true
    vectorsError.value = null
    const response = await fetch('/api/preference-vectors')
    if (!response.ok) throw new Error('Failed to fetch preference vectors')
    vectors.value = await response.json()
  } catch (err) {
    vectorsError.value = err.message
  } finally {
    vectorsLoading.value = false
  }
}

const createVector = async () => {
  if (!newVector.value.title || !newVector.value.description) {
    vectorsError.value = 'Title and description are required'
    return
  }

  try {
    const response = await fetch('/api/preference-vectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newVector.value)
    })
    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to create vector')
    }
    newVector.value = { title: '', description: '' }
    showAddVectorForm.value = false
    await fetchVectors()
  } catch (err) {
    vectorsError.value = err.message
  }
}

const deleteVector = async (id) => {
  if (!confirm('Are you sure you want to delete this vector?')) return
  try {
    const response = await fetch(`/api/preference-vectors/${id}`, { method: 'DELETE' })
    if (!response.ok) throw new Error('Failed to delete vector')
    await fetchVectors()
  } catch (err) {
    vectorsError.value = err.message
  }
}

const startEditVector = (vector) => { editingVectorId.value = vector.id }
const cancelEditVector = () => { editingVectorId.value = null }

const saveEditVector = async (vector) => {
  try {
    const response = await fetch(`/api/preference-vectors/${vector.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: vector.title, description: vector.description })
    })
    if (!response.ok) throw new Error('Failed to update vector')
    editingVectorId.value = null
    await fetchVectors()
  } catch (err) {
    vectorsError.value = err.message
  }
}

// Sources methods
const fetchSources = async () => {
  try {
    sourcesLoading.value = true
    sourcesError.value = null
    const response = await fetch('/api/urls')
    if (!response.ok) throw new Error('Failed to fetch sources')
    sources.value = await response.json()
  } catch (err) {
    sourcesError.value = err.message
  } finally {
    sourcesLoading.value = false
  }
}

const addSource = async () => {
  if (!newSource.value.url) {
    sourcesError.value = 'URL is required'
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
    newSource.value = { url: '', type: 'rss' }
    showAddSourceForm.value = false
    await fetchSources()
  } catch (err) {
    sourcesError.value = err.message
  }
}

const deleteSource = async (id) => {
  if (!confirm('Are you sure you want to delete this source?')) return
  try {
    const response = await fetch(`/api/urls/${id}`, { method: 'DELETE' })
    if (!response.ok) throw new Error('Failed to delete source')
    await fetchSources()
  } catch (err) {
    sourcesError.value = err.message
  }
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

const getDomain = (url) => {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

onMounted(() => {
  checkLogin()
  fetchVectors()
  fetchSources()
})
</script>

<template>
  <div class="container">
    <div class="settings-header">
      <h1>Settings</h1>
      <p class="text-muted">Manage your preferences and news sources</p>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        :class="['tab', { active: activeTab === 'preferences' }]"
        @click="activeTab = 'preferences'"
      >
        Preferences
      </button>
      <button
        :class="['tab', { active: activeTab === 'sources' }]"
        @click="activeTab = 'sources'"
      >
        Sources
      </button>
    </div>

    <!-- Preferences tab -->
    <div v-if="activeTab === 'preferences'" class="tab-content">
      <!-- Error alert -->
      <div v-if="vectorsError" class="alert mb-3">
        <strong>Error:</strong> {{ vectorsError }}
        <button @click="vectorsError = null" class="btn btn-sm btn-outline" style="float: right;">Dismiss</button>
      </div>

      <!-- Add new vector -->
      <div class="card mb-4">
        <div class="card-header">
          <h2>Preference Vectors</h2>
          <button v-if="isLoggedIn && !showAddVectorForm" @click="showAddVectorForm = true" class="btn btn-primary btn-sm">
            + Add Vector
          </button>
        </div>
        <div v-if="isLoggedIn && showAddVectorForm" class="card-body">
          <form @submit.prevent="createVector">
            <div class="form-group mb-3">
              <label>Title</label>
              <input v-model="newVector.title" type="text" placeholder="Enter title" required />
            </div>
            <div class="form-group mb-3">
              <label>Description</label>
              <textarea v-model="newVector.description" rows="4"
                        placeholder="Enter text to generate vector from" required></textarea>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary">Create Vector</button>
              <button type="button" @click="showAddVectorForm = false; newVector = { title: '', description: '' }"
                      class="btn btn-outline">Cancel</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="vectorsLoading" class="loading-container">
        <div class="spinner"></div>
        <p class="text-muted">Loading vectors...</p>
      </div>

      <!-- Vectors list -->
      <div v-else-if="vectors.length > 0" class="card">
        <div class="vectors-table">
          <div v-for="vector in vectors" :key="vector.id" class="vector-row">
            <template v-if="isLoggedIn && editingVectorId === vector.id">
              <div class="vector-edit-form">
                <div class="form-group">
                  <label>Title</label>
                  <input v-model="vector.title" type="text" required />
                </div>
                <div class="form-group">
                  <label>Description</label>
                  <textarea v-model="vector.description" rows="4" required></textarea>
                </div>
                <div class="form-actions">
                  <button @click="saveEditVector(vector)" class="btn btn-primary btn-sm">Save</button>
                  <button @click="cancelEditVector" class="btn btn-outline btn-sm">Cancel</button>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="vector-content">
                <h3>{{ vector.title }}</h3>
                <p class="vector-description">{{ vector.description }}</p>
                <p class="text-muted vector-date">Created: {{ formatDate(vector.created_at) }}</p>
              </div>
              <div v-if="isLoggedIn" class="vector-actions">
                <button @click="startEditVector(vector)" class="btn btn-sm btn-outline">Edit</button>
                <button @click="deleteVector(vector.id)" class="btn btn-sm btn-outline">Delete</button>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="empty-state">
        <p class="text-muted">No preference vectors found.</p>
      </div>
    </div>

    <!-- Sources tab -->
    <div v-if="activeTab === 'sources'" class="tab-content">
      <!-- Error alert -->
      <div v-if="sourcesError" class="alert mb-3">
        <strong>Error:</strong> {{ sourcesError }}
        <button @click="sourcesError = null" class="btn btn-sm btn-outline" style="float: right;">Dismiss</button>
      </div>

      <!-- Add new source -->
      <div class="card mb-4">
        <div class="card-header">
          <h2>News Sources</h2>
          <button v-if="isLoggedIn && !showAddSourceForm" @click="showAddSourceForm = true" class="btn btn-primary btn-sm">
            + Add Source
          </button>
        </div>
        <div v-if="isLoggedIn && showAddSourceForm" class="card-body">
          <form @submit.prevent="addSource">
            <div class="form-group mb-3">
              <label>Source Type</label>
              <select v-model="newSource.type" class="form-select">
                <option value="rss">RSS Feed</option>
                <option value="homepage">Homepage</option>
              </select>
            </div>
            <div class="form-group mb-3">
              <label>{{ newSource.type === 'rss' ? 'RSS Feed URL' : 'Homepage URL' }}</label>
              <input v-model="newSource.url" type="url"
                     :placeholder="newSource.type === 'rss' ? 'https://example.com/feed.xml' : 'https://example.com'" required />
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary">Add Source</button>
              <button type="button" @click="showAddSourceForm = false; newSource = { url: '', type: 'rss' }"
                      class="btn btn-outline">Cancel</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="sourcesLoading" class="loading-container">
        <div class="spinner"></div>
        <p class="text-muted">Loading sources...</p>
      </div>

      <!-- Sources list -->
      <div v-else-if="sources.length > 0" class="card">
        <div class="sources-grid">
          <div v-for="source in sources" :key="source.id" class="source-item">
            <div class="source-content">
              <h3>{{ getDomain(source.url) }}</h3>
              <span class="source-type-badge" :class="source.type">{{ source.type === 'rss' ? 'RSS' : 'Homepage' }}</span>
              <a :href="source.url" target="_blank" rel="noopener noreferrer" class="source-url">
                {{ source.url }}
              </a>
              <p class="text-muted source-date">Added: {{ formatDate(source.created_at) }}</p>
              <p class="text-muted source-date">Last crawled: {{ source.last_crawled_at ? formatDate(source.last_crawled_at) : 'Not yet crawled' }}</p>
            </div>
            <div v-if="isLoggedIn" class="source-actions">
              <button @click="deleteSource(source.id)" class="btn btn-sm btn-outline">Delete</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="empty-icon">
          <path d="M4 11a9 9 0 0 1 9 9"></path>
          <path d="M4 4a16 16 0 0 1 16 16"></path>
          <circle cx="5" cy="19" r="1"></circle>
        </svg>
        <p class="text-muted">No sources configured.</p>
      </div>
    </div>

    <!-- Login section at the bottom -->
    <section class="login-section">
      <div v-if="isLoggedIn" class="login-status">
        <div class="login-status-info">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
          <span>Logged in</span>
        </div>
        <button @click="handleLogout" class="btn btn-outline btn-sm">Logout</button>
      </div>
      <div v-else class="login-form-card">
        <h2>Login</h2>
        <p class="text-muted">Login to edit preference vectors and sources</p>
        <div v-if="loginError" class="alert mb-3">
          <strong>Error:</strong> {{ loginError }}
        </div>
        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label>Email</label>
            <input v-model="loginForm.username" type="text" placeholder="Enter email" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input v-model="loginForm.password" type="password" placeholder="Enter password" required />
          </div>
          <button type="submit" class="btn btn-primary" :disabled="loginLoading">
            {{ loginLoading ? 'Signing in...' : 'Sign in' }}
          </button>
        </form>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-header {
  margin-bottom: 2rem;
}

.settings-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  color: var(--text-color);
}

/* Login section */
.login-section {
  margin-top: 2rem;
}

.login-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.login-status-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-color);
  font-weight: 500;
}

.login-form-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 400px;
}

.login-form-card h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: var(--text-color);
}

.login-form-card > .text-muted {
  margin-bottom: 1.25rem;
  font-size: 0.875rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.login-form .btn {
  margin-top: 0.5rem;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
}

.tab {
  padding: 0.75rem 1.5rem;
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s ease;
}

.tab:hover {
  color: var(--text-color);
}

.tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

/* Tab content */
.tab-content {
  min-height: 200px;
}

/* Cards */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h2 {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.card-body {
  padding: 1.5rem;
}

/* Forms */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-color);
  font-size: 0.875rem;
}

.form-select {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background-color: var(--surface-color);
  color: var(--text-color);
  cursor: pointer;
}

.form-select:focus {
  outline: none;
  border-color: var(--primary-color);
}

.form-actions {
  display: flex;
  gap: 1rem;
}

/* Vectors */
.vectors-table {
  display: flex;
  flex-direction: column;
}

.vector-row {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.vector-row:last-child {
  border-bottom: none;
}

.vector-content {
  flex: 1;
}

.vector-content h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
  color: var(--text-color);
}

.vector-description {
  color: var(--text-muted);
  margin-bottom: 0.375rem;
  font-size: 0.875rem;
  max-width: 600px;
}

.vector-date {
  font-size: 0.8125rem;
}

.vector-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.vector-edit-form {
  width: 100%;
  padding: 1rem;
  background: var(--bg-color);
  border-radius: 6px;
}

/* Sources */
.sources-grid {
  display: flex;
  flex-direction: column;
}

.source-item {
  padding: 1.25rem 1.5rem;
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
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
  color: var(--text-color);
}

.source-type-badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 500;
  border-radius: 4px;
  margin-bottom: 0.375rem;
}

.source-type-badge.rss {
  background-color: rgba(99, 102, 241, 0.1);
  color: var(--primary-color);
}

.source-type-badge.homepage {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.source-url {
  display: block;
  color: var(--primary-color);
  text-decoration: none;
  margin-bottom: 0.375rem;
  word-break: break-all;
  font-size: 0.875rem;
}

.source-url:hover {
  text-decoration: underline;
}

.source-date {
  font-size: 0.8125rem;
}

.source-actions {
  flex-shrink: 0;
}

/* Common */
.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

@media (max-width: 768px) {
  .settings-header h1 {
    font-size: 1.5rem;
  }

  .login-form-card {
    max-width: none;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .vector-row,
  .source-item {
    flex-direction: column;
  }

  .vector-actions,
  .source-actions {
    width: 100%;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions .btn {
    width: 100%;
  }

  .tab {
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
  }
}
</style>
