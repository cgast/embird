<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const topics = ref([])
const topicClusters = ref({})
const loading = ref(true)
const error = ref(null)
const isLoggedIn = ref(false)

// New topic form
const showCreateForm = ref(false)
const newTopic = ref({ name: '', slug: '', description: '' })
const createError = ref(null)
const createLoading = ref(false)

const checkLogin = () => {
  isLoggedIn.value = !!localStorage.getItem('embird_token')
}

const fetchTopics = async () => {
  try {
    loading.value = true
    error.value = null
    const response = await fetch('/api/topics')
    if (!response.ok) throw new Error('Failed to fetch topics')
    topics.value = await response.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

const fetchClustersForTopic = async (topicSlug) => {
  try {
    const response = await fetch(`/api/${topicSlug}/news/clusters`)
    if (!response.ok) return
    const clusters = await response.json()

    // Flatten subclusters same as ClusterHome, then take top 3 by score
    const items = []
    for (const [clusterId, cluster] of Object.entries(clusters)) {
      if (cluster.subclusters && cluster.subclusters.length > 1) {
        for (const sub of cluster.subclusters) {
          items.push({
            id: `${clusterId}-${sub.name}`,
            name: sub.name,
            parentName: cluster.name || `Cluster ${clusterId}`,
            articles: sub.articles || [],
            score: computeScore(sub.articles || [])
          })
        }
      } else {
        items.push({
          id: clusterId,
          name: cluster.name || `Cluster ${clusterId}`,
          parentName: null,
          articles: cluster.articles || [],
          score: computeScore(cluster.articles || [])
        })
      }
    }

    items.sort((a, b) => b.score - a.score)
    topicClusters.value[topicSlug] = items.slice(0, 3)
  } catch (err) {
    console.error(`Error fetching clusters for ${topicSlug}:`, err)
  }
}

function computeScore(articles) {
  if (!articles || articles.length === 0) return 0
  const now = Date.now()
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
  const rawScore = (articles.length * 10) + (totalHits * 2) + (spanHours * 1.5)
  return rawScore * decayFactor
}

const getNewestArticle = (articles) => {
  if (!articles || articles.length === 0) return null
  return articles.reduce((newest, article) => {
    return new Date(article.last_seen_at) > new Date(newest.last_seen_at) ? article : newest
  }, articles[0])
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

const autoSlug = () => {
  newTopic.value.slug = newTopic.value.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

const createTopic = async () => {
  if (!newTopic.value.name || !newTopic.value.slug) {
    createError.value = 'Name and slug are required'
    return
  }
  try {
    createLoading.value = true
    createError.value = null
    const response = await fetch('/api/topics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newTopic.value)
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || 'Failed to create topic')
    }
    newTopic.value = { name: '', slug: '', description: '' }
    showCreateForm.value = false
    await fetchTopics()
  } catch (err) {
    createError.value = err.message
  } finally {
    createLoading.value = false
  }
}

const goToTopic = (slug) => {
  router.push(`/${slug}/`)
}

onMounted(async () => {
  checkLogin()
  await fetchTopics()
  // Fetch clusters for all topics in parallel
  await Promise.all(topics.value.map(t => fetchClustersForTopic(t.slug)))
})
</script>

<template>
  <div class="container">
    <div class="landing-header">
      <h1>Topics</h1>
      <p class="text-muted">All topics and their top stories</p>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading topics...</p>
    </div>

    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <div v-else>
      <!-- Create new topic (admin only) -->
      <div v-if="isLoggedIn" class="create-topic-section">
        <button v-if="!showCreateForm" @click="showCreateForm = true" class="btn btn-primary">
          + New Topic
        </button>
        <div v-if="showCreateForm" class="create-topic-form card">
          <div class="card-body">
            <h2>Create New Topic</h2>
            <div v-if="createError" class="alert mb-3">
              <strong>Error:</strong> {{ createError }}
            </div>
            <form @submit.prevent="createTopic">
              <div class="form-group mb-3">
                <label>Name</label>
                <input v-model="newTopic.name" @input="autoSlug" type="text" placeholder="e.g. Artificial Intelligence" required />
              </div>
              <div class="form-group mb-3">
                <label>Slug</label>
                <input v-model="newTopic.slug" type="text" placeholder="e.g. artificial-intelligence" required />
              </div>
              <div class="form-group mb-3">
                <label>Description (optional)</label>
                <textarea v-model="newTopic.description" rows="2" placeholder="Brief description of the topic"></textarea>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn-primary" :disabled="createLoading">
                  {{ createLoading ? 'Creating...' : 'Create Topic' }}
                </button>
                <button type="button" @click="showCreateForm = false; createError = null" class="btn btn-outline">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      </div>

      <div v-if="topics.length === 0" class="empty-state">
        <p class="text-muted">No topics available.</p>
      </div>

      <div class="topics-grid">
        <div
          v-for="topic in topics"
          :key="topic.slug"
          class="topic-section"
        >
          <div class="topic-section-header" @click="goToTopic(topic.slug)">
            <h2>{{ topic.name }}</h2>
            <p v-if="topic.description" class="text-muted topic-description">{{ topic.description }}</p>
            <span class="view-all">View all stories &rarr;</span>
          </div>

          <div class="topic-clusters">
            <div v-if="!topicClusters[topic.slug]" class="cluster-loading">
              <div class="spinner spinner-sm"></div>
            </div>
            <div v-else-if="topicClusters[topic.slug].length === 0" class="cluster-empty">
              <p class="text-muted">No stories yet.</p>
            </div>
            <div
              v-else
              v-for="(cluster, idx) in topicClusters[topic.slug]"
              :key="cluster.id"
              class="cluster-card"
              @click="goToTopic(topic.slug)"
            >
              <div class="cluster-rank">#{{ idx + 1 }}</div>
              <div class="cluster-content">
                <h3 v-if="getNewestArticle(cluster.articles)">{{ getNewestArticle(cluster.articles).title }}</h3>
                <h3 v-else>{{ cluster.name }}</h3>
                <div class="cluster-meta">
                  <span class="tag tag-count">{{ cluster.articles.length }} article{{ cluster.articles.length !== 1 ? 's' : '' }}</span>
                  <span v-if="getNewestArticle(cluster.articles)" class="text-muted cluster-time">
                    {{ formatRelativeTime(getNewestArticle(cluster.articles).last_seen_at) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.landing-header {
  margin-bottom: 2rem;
}

.landing-header h1 {
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

.create-topic-section {
  margin-bottom: 2rem;
}

.create-topic-form {
  margin-top: 1rem;
  max-width: 500px;
}

.create-topic-form h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.topics-grid {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.topic-section {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow);
}

.topic-section-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.topic-section-header:hover {
  background-color: var(--bg-color);
}

.topic-section-header h2 {
  font-size: 1.375rem;
  font-weight: 700;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.topic-description {
  font-size: 0.875rem;
  margin-bottom: 0.375rem;
}

.view-all {
  font-size: 0.8125rem;
  color: var(--primary-color);
  font-weight: 500;
}

.topic-clusters {
  display: flex;
  flex-direction: column;
}

.cluster-loading {
  padding: 2rem;
  text-align: center;
}

.cluster-empty {
  padding: 1.5rem;
  text-align: center;
}

.cluster-card {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.cluster-card:last-child {
  border-bottom: none;
}

.cluster-card:hover {
  background-color: var(--bg-color);
}

.cluster-rank {
  flex-shrink: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--primary-color);
  opacity: 0.6;
  min-width: 1.75rem;
  padding-top: 0.125rem;
}

.cluster-content {
  flex: 1;
  min-width: 0;
}

.cluster-content h3 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-color);
  line-height: 1.3;
  margin-bottom: 0.375rem;
}

.cluster-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
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

.tag-count {
  background: var(--primary-color);
  color: white;
}

.cluster-time {
  font-size: 0.8125rem;
}

.spinner-sm {
  width: 20px;
  height: 20px;
}

/* Form styles matching Settings.vue */
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
  font-size: 0.875rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
}

@media (max-width: 768px) {
  .landing-header h1 {
    font-size: 1.5rem;
  }

  .topic-section-header {
    padding: 1rem 1.25rem;
  }

  .topic-section-header h2 {
    font-size: 1.125rem;
  }

  .cluster-card {
    padding: 0.875rem 1.25rem;
  }

  .create-topic-form {
    max-width: none;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions .btn {
    width: 100%;
  }
}
</style>
