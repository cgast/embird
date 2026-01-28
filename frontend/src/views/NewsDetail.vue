<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const newsItem = ref(null)
const relatedItems = ref([])
const loading = ref(true)
const error = ref(null)

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

const sourceDomain = ref('')

const fetchNewsDetail = async () => {
  try {
    loading.value = true
    error.value = null

    const newsId = route.params.id
    const response = await fetch(`/api/news/${newsId}`)
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('News article not found')
      }
      throw new Error('Failed to fetch news details')
    }

    newsItem.value = await response.json()

    // Extract domain
    try {
      const url = new URL(newsItem.value.source_url)
      sourceDomain.value = url.hostname.replace('www.', '')
    } catch {
      sourceDomain.value = newsItem.value.source_url
    }

    // Fetch related news (same source)
    const relatedResponse = await fetch(
      `/api/news?source_url=${encodeURIComponent(newsItem.value.source_url)}&limit=5`
    )
    if (relatedResponse.ok) {
      const allFromSource = await relatedResponse.json()
      relatedItems.value = allFromSource
        .filter(item => item.id !== newsItem.value.id)
        .slice(0, 5)
    }

  } catch (err) {
    error.value = err.message
    console.error('Error fetching news detail:', err)
  } finally {
    loading.value = false
  }
}

const goToSource = () => {
  router.push({ name: 'news', query: { source_url: newsItem.value.source_url } })
}

onMounted(() => {
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
      <button class="btn btn-primary mt-2" @click="router.push('/')">Back to Dashboard</button>
    </div>

    <!-- News detail -->
    <div v-else-if="newsItem" class="news-detail">
      <div class="row">
        <div class="col-md-8">
          <article class="article-card">
            <h1 class="article-title">{{ newsItem.title }}</h1>

            <div class="article-meta">
              <span class="badge">{{ sourceDomain }}</span>
              <span class="badge badge-secondary">{{ newsItem.hit_count }} hits</span>
            </div>

            <div class="article-summary">
              <h2>Summary</h2>
              <p>{{ newsItem.summary }}</p>
            </div>

            <div class="article-info">
              <p><strong>First seen:</strong> {{ formatDate(newsItem.first_seen_at) }}</p>
              <p><strong>Last seen:</strong> {{ formatDate(newsItem.last_seen_at) }}</p>
            </div>

            <div class="article-actions">
              <a :href="newsItem.url" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                Read Full Article
              </a>
              <button @click="goToSource" class="btn btn-outline">
                More from this Source
              </button>
            </div>
          </article>
        </div>

        <div class="col-md-4">
          <aside class="sidebar-card">
            <h2 class="sidebar-title">Related News</h2>
            <div v-if="relatedItems.length > 0" class="related-list">
              <router-link
                v-for="item in relatedItems"
                :key="item.id"
                :to="`/news/${item.id}`"
                class="related-item"
              >
                <h3>{{ item.title }}</h3>
                <p class="text-muted">
                  {{ new Date(item.first_seen_at).toLocaleDateString() }} · {{ item.hit_count }} hits
                </p>
              </router-link>
            </div>
            <p v-else class="text-muted">No related news available.</p>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.news-detail {
  margin-top: 1rem;
}

.article-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: var(--shadow);
}

.article-title {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 1rem;
  color: var(--text-color);
  line-height: 1.3;
}

.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.article-summary {
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  background: var(--bg-color);
  border-radius: 8px;
}

.article-summary h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.article-summary p {
  color: var(--text-color);
  line-height: 1.6;
}

.article-info {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--bg-color);
  border-radius: 8px;
}

.article-info p {
  margin-bottom: 0.5rem;
  color: var(--text-muted);
}

.article-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.sidebar-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: var(--shadow);
  position: sticky;
  top: 80px;
}

.sidebar-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.related-item {
  padding: 1rem;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.related-item:hover {
  border-color: var(--primary-color);
  transform: translateX(4px);
}

.related-item h3 {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-color);
  line-height: 1.4;
}

.related-item p {
  font-size: 0.75rem;
}

@media (max-width: 768px) {
  .article-card {
    padding: 1.5rem;
  }

  .article-title {
    font-size: 1.5rem;
  }

  .article-summary h2 {
    font-size: 1.125rem;
  }

  .article-actions {
    flex-direction: column;
  }

  .article-actions .btn {
    width: 100%;
  }

  .sidebar-card {
    position: static;
    margin-top: 2rem;
  }
}
</style>
