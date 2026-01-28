import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// Import views
import Dashboard from './views/Dashboard.vue'
import NewsList from './views/NewsList.vue'
import NewsDetail from './views/NewsDetail.vue'
import NewsClusters from './views/NewsClusters.vue'
import Search from './views/Search.vue'
import UmapVisual from './views/UmapVisual.vue'
import PreferenceVectors from './views/PreferenceVectors.vue'
import Sources from './views/Sources.vue'

// Define routes
const routes = [
  { path: '/', name: 'dashboard', component: Dashboard },
  { path: '/news', name: 'news', component: NewsList },
  { path: '/news/:id', name: 'news-detail', component: NewsDetail },
  { path: '/clusters', name: 'clusters', component: NewsClusters },
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
