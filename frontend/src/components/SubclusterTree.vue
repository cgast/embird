<script>
export default { name: 'SubclusterTree' }
</script>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const props = defineProps({
  subclusters: { type: Array, required: true },
  depth: { type: Number, default: 0 }
})

const expandedSubs = ref(new Set())

const toggleSub = (index) => {
  if (expandedSubs.value.has(index)) {
    expandedSubs.value.delete(index)
  } else {
    expandedSubs.value.add(index)
  }
  expandedSubs.value = new Set(expandedSubs.value)
}

const isSubExpanded = (index) => expandedSubs.value.has(index)

const goToArticle = (id, event) => {
  event.stopPropagation()
  router.push(`/news/${id}`)
}

const sourceDomain = (sourceUrl) => {
  try {
    const url = new URL(sourceUrl)
    return url.hostname.replace('www.', '')
  } catch {
    return sourceUrl
  }
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

const hasChildren = (sub) => sub.subclusters && sub.subclusters.length > 1
</script>

<template>
  <div class="subclusters-list">
    <div
      v-for="(sub, index) in subclusters"
      :key="index"
      class="subcluster-node"
      :class="{ 'has-children': hasChildren(sub) }"
    >
      <div class="subcluster-header" @click="toggleSub(index)">
        <div class="subcluster-info">
          <span class="subcluster-name" :class="`depth-${Math.min(depth, 3)}`">{{ sub.name }}</span>
          <div class="subcluster-meta">
            <span class="badge badge-info">{{ sub.articles.length }} article{{ sub.articles.length !== 1 ? 's' : '' }}</span>
            <span v-if="hasChildren(sub)" class="badge badge-subtle">{{ sub.subclusters.length }} subtopics</span>
          </div>
        </div>
        <div class="expand-icon" :class="{ 'expanded': isSubExpanded(index) }">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
      </div>

      <div v-if="isSubExpanded(index)" class="subcluster-content">
        <!-- Recursive: if this subcluster has children, render them -->
        <template v-if="hasChildren(sub)">
          <SubclusterTree
            :subclusters="sub.subclusters"
            :depth="depth + 1"
          />
        </template>

        <!-- Leaf: render articles directly -->
        <template v-else>
          <div
            v-for="item in sub.articles"
            :key="item.id"
            class="cluster-item"
            @click="goToArticle(item.id, $event)"
          >
            <div class="item-header">
              <span class="badge">{{ sourceDomain(item.source_url) }}</span>
              <span class="badge badge-secondary">{{ item.hit_count }} hits</span>
              <span v-if="item.similarity" class="badge">
                {{ Math.round(item.similarity * 100) }}% match
              </span>
            </div>
            <h3 class="item-title">{{ item.title }}</h3>
            <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
            <p class="text-muted item-date">{{ formatRelativeTime(item.first_seen_at) }}</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subclusters-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.subcluster-node {
  border-left: 3px solid var(--primary-color, #222222);
  padding-left: 0.75rem;
  border-radius: 0 4px 4px 0;
}

.subcluster-node.has-children {
  border-left-color: var(--primary-color, #222222);
}

.subcluster-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 0.75rem;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s ease;
  background: rgba(0, 0, 0, 0.03);
}

.subcluster-header:hover {
  background: rgba(0, 0, 0, 0.06);
}

.subcluster-info {
  flex: 1;
  min-width: 0;
}

.subcluster-name {
  font-weight: 600;
  color: var(--text-color, #222222);
  font-size: 0.9375rem;
  display: block;
  margin-bottom: 0.25rem;
}

.subcluster-name.depth-1 {
  color: var(--text-color);
}

.subcluster-name.depth-2 {
  color: var(--secondary-color, #666666);
}

.subcluster-name.depth-3 {
  color: var(--text-muted, #888888);
}

.subcluster-meta {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge-info {
  background: rgba(0, 0, 0, 0.08);
  color: var(--text-color, #222222);
}

.badge-subtle {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-muted, #888888);
}

.expand-icon {
  flex-shrink: 0;
  color: var(--text-muted, #6b7280);
  transition: transform 0.2s ease;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.subcluster-content {
  padding: 0.5rem 0 0.25rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.cluster-item {
  padding: 0.875rem;
  background: var(--surface-color, white);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cluster-item:hover {
  border-color: var(--primary-color, #4f46e5);
  transform: translateX(4px);
  box-shadow: var(--shadow, 0 1px 3px rgba(0,0,0,0.1));
}

.item-header {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.item-title {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-bottom: 0.375rem;
  color: var(--text-color, #111827);
  line-height: 1.4;
}

.item-summary {
  color: var(--text-muted, #6b7280);
  margin-bottom: 0.375rem;
  font-size: 0.8125rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-date {
  font-size: 0.75rem;
}

@media (max-width: 768px) {
  .subcluster-header {
    padding: 0.5rem;
  }

  .subcluster-name {
    font-size: 0.875rem;
  }

  .cluster-item {
    padding: 0.75rem;
  }

  .item-title {
    font-size: 0.875rem;
  }
}
</style>
