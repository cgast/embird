import { computed } from 'vue'
import { useRoute } from 'vue-router'

/**
 * Composable that provides topic-scoped API URL building.
 * Uses the current route's topicSlug param.
 */
export function useTopicApi() {
  const route = useRoute()

  const topicSlug = computed(() => route.params.topicSlug || 'default')

  /**
   * Build an API URL scoped to the current topic.
   * e.g. apiUrl('/news/clusters') => '/api/default/news/clusters'
   */
  const apiUrl = (path) => `/api/${topicSlug.value}${path}`

  /**
   * Build a frontend route path scoped to the current topic.
   * e.g. topicPath('/news/123') => '/default/news/123'
   */
  const topicPath = (path) => `/${topicSlug.value}${path}`

  return { topicSlug, apiUrl, topicPath }
}
