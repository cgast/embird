<script setup>
import { ref, onMounted, computed } from 'vue'

const stats = ref(null)
const loading = ref(true)
const error = ref(null)

const fetchStats = async () => {
  try {
    loading.value = true
    const response = await fetch('/api/news/stats')
    if (!response.ok) throw new Error('Failed to fetch stats')
    stats.value = await response.json()
  } catch (err) {
    error.value = err.message
    console.error('Error fetching stats:', err)
  } finally {
    loading.value = false
  }
}

const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A'
  const d = new Date(isoString)
  return d.toLocaleString()
}

const formatRelativeTime = (isoString) => {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${Math.floor(diffMs / 86400000)}d ago`
}

const sourceDomain = (sourceUrl) => {
  try {
    return new URL(sourceUrl).hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
}

// Compute max value for timeline bar chart scaling
const timelineMax = computed(() => {
  if (!stats.value || !stats.value.activity_timeline) return 1
  return Math.max(...stats.value.activity_timeline.map(t => t.count), 1)
})

const formatHour = (isoString) => {
  const d = new Date(isoString)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
}

const formatDate = (isoString) => {
  const d = new Date(isoString)
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

onMounted(() => {
  fetchStats()
})
</script>

<template>
  <div class="container">
    <div class="dashboard-header">
      <h1>System Dashboard</h1>
      <p class="text-muted">Internals: crawl activity, story lifecycle, cluster generation</p>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading system stats...</p>
    </div>

    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <div v-else-if="stats" class="dashboard-grid">
      <!-- Overview stats -->
      <section class="section">
        <h2 class="section-title">Overview</h2>
        <div class="stats-row">
          <div class="stat-pill">
            <span class="stat-val">{{ stats.total_articles }}</span>
            <span class="stat-lbl">Total articles</span>
          </div>
          <div class="stat-pill">
            <span class="stat-val">{{ stats.articles_24h }}</span>
            <span class="stat-lbl">Last 24h</span>
          </div>
          <div class="stat-pill">
            <span class="stat-val">{{ stats.articles_48h }}</span>
            <span class="stat-lbl">Last 48h</span>
          </div>
          <div class="stat-pill">
            <span class="stat-val">{{ stats.unique_sources }}</span>
            <span class="stat-lbl">Sources</span>
          </div>
          <div class="stat-pill">
            <span class="stat-val">{{ stats.trending_count }}</span>
            <span class="stat-lbl">Multi-hit</span>
          </div>
          <div class="stat-pill">
            <span class="stat-val">{{ stats.avg_hit_count }}</span>
            <span class="stat-lbl">Avg hits</span>
          </div>
        </div>
      </section>

      <!-- Crawl Activity Timeline -->
      <section class="section">
        <h2 class="section-title">Crawl Activity (last 48h)</h2>
        <p class="text-muted section-sub">
          Last article pulled: <strong>{{ formatRelativeTime(stats.newest_article_at) }}</strong>
          <span v-if="stats.newest_article_at"> ({{ formatDateTime(stats.newest_article_at) }})</span>
        </p>
        <div v-if="stats.activity_timeline && stats.activity_timeline.length > 0" class="timeline-chart">
          <div
            v-for="(entry, i) in stats.activity_timeline"
            :key="i"
            class="timeline-bar-wrapper"
            :title="`${formatDate(entry.hour)} ${formatHour(entry.hour)}: ${entry.count} articles`"
          >
            <div
              class="timeline-bar"
              :style="{ height: Math.max((entry.count / timelineMax) * 100, 2) + '%' }"
            ></div>
            <span v-if="i % 6 === 0" class="timeline-label">{{ formatHour(entry.hour) }}</span>
          </div>
        </div>
        <p v-else class="text-muted">No timeline data available.</p>
      </section>

      <!-- Story Lifespan -->
      <section class="section">
        <h2 class="section-title">Story Lifespan</h2>
        <p class="text-muted section-sub">How long stories remain active (last_seen - first_seen), last 48h</p>
        <div v-if="stats.lifespan_distribution && stats.lifespan_distribution.length > 0" class="lifespan-chart">
          <div
            v-for="bucket in stats.lifespan_distribution"
            :key="bucket.bucket"
            class="lifespan-row"
          >
            <span class="lifespan-label">{{ bucket.bucket }}</span>
            <div class="lifespan-bar-track">
              <div
                class="lifespan-bar"
                :style="{
                  width: Math.max((bucket.count / Math.max(...stats.lifespan_distribution.map(b => b.count))) * 100, 2) + '%'
                }"
              ></div>
            </div>
            <span class="lifespan-count">{{ bucket.count }}</span>
          </div>
        </div>
        <p v-else class="text-muted">No lifespan data available.</p>
      </section>

      <!-- Cluster Generation Info -->
      <section class="section">
        <h2 class="section-title">Cluster Generation</h2>
        <div v-if="stats.cluster_info" class="cluster-meta-grid">
          <div class="meta-item">
            <span class="meta-label">Last generated</span>
            <span class="meta-value">{{ formatRelativeTime(stats.cluster_info.generated_at) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Clusters</span>
            <span class="meta-value">{{ stats.cluster_info.num_clusters }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Clustered articles</span>
            <span class="meta-value">{{ stats.cluster_info.total_articles_clustered }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Time range</span>
            <span class="meta-value">{{ stats.cluster_info.hours }}h</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Min similarity</span>
            <span class="meta-value">{{ stats.cluster_info.min_similarity }}</span>
          </div>
        </div>
        <p v-else class="text-muted">No cluster data available.</p>
      </section>

      <!-- Top Sources -->
      <section class="section">
        <h2 class="section-title">Top Sources (48h)</h2>
        <div v-if="stats.top_sources && stats.top_sources.length > 0" class="sources-table">
          <div
            v-for="src in stats.top_sources"
            :key="src.source_url"
            class="source-row"
          >
            <span class="source-name">{{ sourceDomain(src.source_url) }}</span>
            <div class="source-bar-track">
              <div
                class="source-bar"
                :style="{
                  width: Math.max((src.count / stats.top_sources[0].count) * 100, 2) + '%'
                }"
              ></div>
            </div>
            <span class="source-count">{{ src.count }}</span>
          </div>
        </div>
        <p v-else class="text-muted">No source data available.</p>
      </section>
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
  margin-bottom: 0.25rem;
  color: var(--text-color);
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.dashboard-grid {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.section {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: var(--shadow);
}

.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.5rem;
}

.section-sub {
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.section-sub strong {
  color: var(--text-color);
}

/* Stats row */
.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.stat-val {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--primary-color);
}

.stat-lbl {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* Timeline chart */
.timeline-chart {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 120px;
  padding-top: 0.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1.25rem;
  overflow-x: auto;
}

.timeline-bar-wrapper {
  flex: 1;
  min-width: 4px;
  max-width: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  position: relative;
}

.timeline-bar {
  width: 100%;
  background: var(--primary-color);
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: height 0.3s ease;
}

.timeline-label {
  position: absolute;
  bottom: -1.125rem;
  font-size: 0.5625rem;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Lifespan chart */
.lifespan-chart {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.lifespan-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.lifespan-label {
  width: 4rem;
  flex-shrink: 0;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-color);
  text-align: right;
}

.lifespan-bar-track {
  flex: 1;
  height: 20px;
  background: var(--bg-color);
  border-radius: 4px;
  overflow: hidden;
}

.lifespan-bar {
  height: 100%;
  background: var(--primary-color);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.lifespan-count {
  width: 2.5rem;
  flex-shrink: 0;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
  text-align: right;
}

/* Cluster meta */
.cluster-meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.meta-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  color: var(--text-muted);
}

.meta-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-color);
}

/* Sources table */
.sources-table {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.source-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.source-name {
  width: 10rem;
  flex-shrink: 0;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-bar-track {
  flex: 1;
  height: 16px;
  background: var(--bg-color);
  border-radius: 4px;
  overflow: hidden;
}

.source-bar {
  height: 100%;
  background: var(--primary-color);
  border-radius: 4px;
  transition: width 0.3s ease;
  opacity: 0.7;
}

.source-count {
  width: 2.5rem;
  flex-shrink: 0;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
  text-align: right;
}

@media (max-width: 768px) {
  .dashboard-header h1 {
    font-size: 1.5rem;
  }

  .section {
    padding: 1rem;
  }

  .source-name {
    width: 6rem;
  }

  .lifespan-label {
    width: 3rem;
    font-size: 0.75rem;
  }
}
</style>
