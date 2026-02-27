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

// Define routes
const routes = [
  { path: '/', name: 'topnews', component: ClusterHome },
  { path: '/newnews', name: 'newnews', component: Archive },
  { path: '/wall', name: 'wall', component: WallOfNews },
  { path: '/cluster/:id', name: 'cluster-detail', component: ClusterDetail },
  { path: '/system', name: 'system', component: Dashboard },
  { path: '/news/:id', name: 'news-detail', component: NewsDetail },
  { path: '/settings', name: 'settings', component: Settings },
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
