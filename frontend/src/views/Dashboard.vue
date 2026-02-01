<script setup>
import { ref, onMounted } from 'vue'
import NewsCard from '../components/NewsCard.vue'

const news = ref([])
const loading = ref(true)
const error = ref(null)
const stats = ref({
  total: 0,
  sources: 0,
  trending: 0
})

const fetchDashboardData = async () => {
  try {
    loading.value = true

    // Fetch trending news (last 24 hours)
    const response = await fetch('/api/news/trending?hours=24&limit=20')
    if (!response.ok) throw new Error('Failed to fetch news')

    news.value = await response.json()

    // Calculate stats
    stats.value.total = news.value.length
    stats.value.sources = new Set(news.value.map(item => item.source_url)).size
    stats.value.trending = news.value.filter(item => item.hit_count > 1).length

  } catch (err) {
    error.value = err.message
    console.error('Error fetching dashboard data:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<template>
  <div class="container">
    <div class="dashboard-header">
      <h1>Dashboard</h1>
      <p class="text-muted">Latest news from the last 24 hours</p>
    </div>

    <!-- Stats cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">Total Articles</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.sources }}</div>
        <div class="stat-label">Sources</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.trending }}</div>
        <div class="stat-label">Trending</div>
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
.dashboard-header {
  margin-bottom: 2rem;
}

.dashboard-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.stats-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  box-shadow: var(--shadow);
  transition: all 0.2s ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-hover);
  border-color: var(--primary-color);
}

.stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--primary-color);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
  .dashboard-header h1 {
    font-size: 1.5rem;
  }
}
</style>
