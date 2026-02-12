import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Import views
import ClusterHome from './views/ClusterHome.vue'
import Dashboard from './views/Dashboard.vue'
import Archive from './views/Archive.vue'
import NewsDetail from './views/NewsDetail.vue'
import Settings from './views/Settings.vue'

// Define routes
const routes = [
  { path: '/', name: 'home', component: ClusterHome },
  { path: '/dashboard', name: 'dashboard', component: Dashboard },
  { path: '/archive', name: 'archive', component: Archive },
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
