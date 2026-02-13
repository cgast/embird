<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const newsItem = ref(null)
const relatedItems = ref([])
const similarItems = ref([])
const loading = ref(true)
const error = ref(null)

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
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

const sourceDomain = ref('')

const lifetimeHours = computed(() => {
  if (!newsItem.value) return 0
  const first = new Date(newsItem.value.first_seen_at)
  const last = new Date(newsItem.value.last_seen_at)
  const diffMs = last - first
  return Math.round(diffMs / 3600000 * 10) / 10
})

const fetchNewsDetail = async () => {
  try {
    loading.value = true
    error.value = null

    const newsId = route.params.id
    const response = await fetch(`/api/news/${newsId}`)
    if (!response.ok) {
      if (response.status === 404) throw new Error('News article not found')
      throw new Error('Failed to fetch news details')
    }

    newsItem.value = await response.json()

    try {
      const url = new URL(newsItem.value.source_url)
      sourceDomain.value = url.hostname.replace('www.', '')
    } catch {
      sourceDomain.value = newsItem.value.source_url
    }

    // Fetch related news (same source) and similar news (all sources) in parallel
    const [relatedResponse, similarResponse] = await Promise.all([
      fetch(`/api/news?source_url=${encodeURIComponent(newsItem.value.source_url)}&limit=5`),
      fetch(`/api/news/${newsId}/similar?limit=5`)
    ])

    if (relatedResponse.ok) {
      const allFromSource = await relatedResponse.json()
      relatedItems.value = allFromSource
        .filter(item => item.id !== newsItem.value.id)
        .slice(0, 5)
    }

    if (similarResponse.ok) {
      similarItems.value = await similarResponse.json()
    }
  } catch (err) {
    error.value = err.message
    console.error('Error fetching news detail:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchNewsDetail()
})

watch(() => route.params.id, () => {
  fetchNewsDetail()
})
</script>

<template>
  <div class="container">
    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading article...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
      <button class="btn btn-primary mt-2" @click="router.push('/')">Back to Home</button>
    </div>

    <!-- Article view -->
    <div v-else-if="newsItem" class="article-layout">
      <article class="article">
        <header class="article-header">
          <div class="article-source">
            <router-link :to="{ name: 'archive', query: { source_url: newsItem.source_url } }" class="source-domain">{{ sourceDomain }}</router-link>
            <span class="separator">&middot;</span>
            <span class="hit-count">{{ newsItem.hit_count }} hit{{ newsItem.hit_count !== 1 ? 's' : '' }}</span>
          </div>
          <h1 class="article-title">
            <a :href="newsItem.url" target="_blank" rel="noopener noreferrer">{{ newsItem.title }}</a>
          </h1>
        </header>

        <div v-if="newsItem.summary" class="article-body">
          <p>{{ newsItem.summary }}</p>
        </div>

        <footer class="article-footer">
          <div class="article-meta-row">
            <span class="timestamp">First seen {{ formatDate(newsItem.first_seen_at) }}</span>
            <span class="separator">&middot;</span>
            <span class="timestamp">Last seen {{ formatDate(newsItem.last_seen_at) }}</span>
            <span class="lifetime-tag">{{ lifetimeHours }}h online</span>
            <a :href="newsItem.url" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">
              Read Full Article
            </a>
          </div>
        </footer>
      </article>

      <div class="sidebar-columns">
        <aside v-if="relatedItems.length > 0" class="related">
          <h2 class="related-title">More from {{ sourceDomain }}</h2>
          <router-link
            v-for="item in relatedItems"
            :key="item.id"
            :to="`/news/${item.id}`"
            class="related-item"
          >
            <h3>{{ item.title }}</h3>
            <span class="text-muted related-meta">
              {{ formatRelativeTime(item.first_seen_at) }} &middot; {{ item.hit_count }} hit{{ item.hit_count !== 1 ? 's' : '' }}
            </span>
          </router-link>
        </aside>

        <aside v-if="similarItems.length > 0" class="related">
          <h2 class="related-title">Related from all sources</h2>
          <router-link
            v-for="item in similarItems"
            :key="item.id"
            :to="`/news/${item.id}`"
            class="related-item"
          >
            <h3>{{ item.title }}</h3>
            <span class="text-muted related-meta">
              {{ item.source_url }} &middot; {{ formatRelativeTime(item.first_seen_at) }}
            </span>
          </router-link>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.article-layout {
  max-width: 720px;
  margin: 0 auto;
}

/* Article */
.article {
  margin-bottom: 3rem;
}

.article-header {
  margin-bottom: 2rem;
}

.article-source {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.source-domain {
  font-weight: 600;
  color: var(--primary-color);
  text-decoration: none;
}

.source-domain:hover {
  text-decoration: underline;
}

.separator {
  opacity: 0.4;
}

.article-title {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.3;
}

.article-title a {
  color: var(--text-color);
  text-decoration: none;
}

.article-title a:hover {
  color: var(--primary-color);
}

.article-body {
  margin-bottom: 2rem;
}

.article-body p {
  font-size: 1.125rem;
  line-height: 1.8;
  color: var(--text-color);
}

.article-footer {
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
}

.article-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: var(--text-muted);
}

.timestamp {
  white-space: nowrap;
}

.lifetime-tag {
  display: inline-block;
  padding: 0.15em 0.5em;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 4px;
  background-color: var(--primary-color);
  color: #fff;
  white-space: nowrap;
}

.btn-sm {
  margin-left: auto;
  padding: 0.3em 0.75em;
  font-size: 0.8125rem;
  white-space: nowrap;
}

/* Sidebar columns */
.sidebar-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--border-color);
}

/* Related */
.related-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.related-item {
  display: block;
  padding: 1rem 0;
  text-decoration: none;
  border-bottom: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.related-item:last-child {
  border-bottom: none;
}

.related-item:hover {
  padding-left: 0.5rem;
}

.related-item h3 {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: var(--text-color);
  line-height: 1.4;
}

.related-meta {
  font-size: 0.75rem;
}

@media (max-width: 768px) {
  .article-title {
    font-size: 1.5rem;
  }

  .article-body p {
    font-size: 1rem;
    line-height: 1.7;
  }

  .article-meta-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .article-meta-row .separator {
    display: none;
  }

  .btn-sm {
    margin-left: 0;
    margin-top: 0.5rem;
  }

  .sidebar-columns {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
}
</style>
