import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Import views
import ClusterHome from './views/ClusterHome.vue'
import Dashboard from './views/Dashboard.vue'
import Archive from './views/Archive.vue'
import WallOfNews from './views/WallOfNews.vue'
import NewsDetail from './views/NewsDetail.vue'
import ClusterDetail from './views/ClusterDetail.vue'
import Settings from './views/Settings.vue'

// Define routes — all scoped under /:topicSlug
const routes = [
  { path: '/', redirect: '/default/' },
  { path: '/:topicSlug/', name: 'topnews', component: ClusterHome },
  { path: '/:topicSlug/newnews', name: 'newnews', component: Archive },
  { path: '/:topicSlug/wall', name: 'wall', component: WallOfNews },
  { path: '/:topicSlug/cluster/:id', name: 'cluster-detail', component: ClusterDetail },
  { path: '/:topicSlug/system', name: 'system', component: Dashboard },
  { path: '/:topicSlug/news/:id', name: 'news-detail', component: NewsDetail },
  { path: '/:topicSlug/settings', name: 'settings', component: Settings },
]

// Create router
const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Create app
const app = createApp(App)
app.use(router)
app.mount('#app')
