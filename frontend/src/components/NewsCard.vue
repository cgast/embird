<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  newsItem: {
    type: Object,
    required: true
  },
  showSimilarity: {
    type: Boolean,
    default: false
  }
})

const router = useRouter()

const formatDate = (dateString) => {
  const date = new Date(dateString)
  const now = new Date()
  const diff = Math.floor((now - date) / 1000) // seconds

  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`

  return date.toLocaleDateString()
}

const sourceDomain = computed(() => {
  try {
    const url = new URL(props.newsItem.source_url)
    return url.hostname.replace('www.', '')
  } catch {
    return props.newsItem.source_url
  }
})

const goToDetail = () => {
  router.push(`/news/${props.newsItem.id}`)
}
</script>

<template>
  <div class="news-card" @click="goToDetail">
    <div class="news-card-header">
      <span class="badge">{{ sourceDomain }}</span>
      <span class="badge badge-secondary">{{ newsItem.hit_count }} hits</span>
      <span v-if="showSimilarity && newsItem.similarity" class="badge">
        {{ Math.round(newsItem.similarity * 100) }}% match
      </span>
    </div>

    <h3 class="news-card-title">{{ newsItem.title }}</h3>

    <p v-if="newsItem.summary" class="news-card-summary">{{ newsItem.summary }}</p>

    <div class="news-card-footer">
      <span class="text-muted">{{ formatDate(newsItem.last_seen_at || newsItem.first_seen_at) }}</span>
      <a :href="newsItem.url" target="_blank" rel="noopener noreferrer"
         class="btn btn-sm btn-outline"
         @click.stop>
        Read article
      </a>
    </div>
  </div>
</template>

<style scoped>
.news-card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  box-shadow: var(--shadow);
  transition: all 0.2s ease;
  cursor: pointer;
}

.news-card:hover {
  box-shadow: var(--shadow-hover);
  transform: translateY(-2px);
  border-color: var(--primary-color);
}

.news-card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.news-card-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  color: var(--text-color);
  line-height: 1.4;
}

.news-card-summary {
  color: var(--text-muted);
  margin-bottom: 1rem;
  font-size: 0.9375rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
}

@media (max-width: 768px) {
  .news-card {
    padding: 1rem;
  }

  .news-card-title {
    font-size: 1rem;
  }

  .news-card-footer {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}
</style>
