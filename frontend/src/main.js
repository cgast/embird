import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Import views
import ClusterHome from './views/ClusterHome.vue'
import Dashboard from './views/Dashboard.vue'
import NewsList from './views/NewsList.vue'
import NewsDetail from './views/NewsDetail.vue'
import Search from './views/Search.vue'
import UmapVisual from './views/UmapVisual.vue'
import PreferenceVectors from './views/PreferenceVectors.vue'
import Sources from './views/Sources.vue'

// Define routes
const routes = [
  { path: '/', name: 'home', component: ClusterHome },
  { path: '/dashboard', name: 'dashboard', component: Dashboard },
  { path: '/news', name: 'news', component: NewsList },
  { path: '/news/:id', name: 'news-detail', component: NewsDetail },
  { path: '/search', name: 'search', component: Search },
  { path: '/umap', name: 'umap', component: UmapVisual },
  { path: '/preference-vectors', name: 'preferences', component: PreferenceVectors },
  { path: '/urls', name: 'sources', component: Sources },
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
