<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const theme = ref('light')
const mobileMenuOpen = ref(false)

// Theme toggle
const toggleTheme = () => {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('theme', theme.value)
}

// Initialize theme from localStorage
onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'light'
  theme.value = savedTheme
  document.documentElement.setAttribute('data-theme', savedTheme)
})

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}
</script>

<template>
  <div id="app">
    <!-- Navbar -->
    <nav class="navbar">
      <div class="container navbar-container">
        <router-link to="/" class="navbar-brand">
          <img src="/embird-logo-bird-v2.png" alt="EmBird" class="logo" />
          <img src="/embird-text.svg" alt="embird" class="logo-text" />
        </router-link>

        <!-- Mobile menu button -->
        <button class="mobile-menu-btn" @click="toggleMobileMenu">
          <svg v-if="!mobileMenuOpen" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>

        <!-- Desktop menu -->
        <div class="navbar-menu desktop-menu">
          <router-link to="/" :class="{ active: route.name === 'topnews' }">TopNews</router-link>
          <router-link to="/newnews" :class="{ active: route.name === 'newnews' }">NewNews</router-link>
          <router-link to="/wall" :class="{ active: route.name === 'wall' }">WallOfNews</router-link>
          <router-link to="/system" :class="{ active: route.name === 'system' }">System</router-link>
          <router-link to="/settings" :class="{ active: route.name === 'settings' }">Settings</router-link>

          <button @click="toggleTheme" class="theme-toggle">
            <svg v-if="theme === 'light'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"></circle>
              <line x1="12" y1="1" x2="12" y2="3"></line>
              <line x1="12" y1="21" x2="12" y2="23"></line>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
              <line x1="1" y1="12" x2="3" y2="12"></line>
              <line x1="21" y1="12" x2="23" y2="12"></line>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
          </button>
        </div>

        <!-- Mobile menu -->
        <div v-if="mobileMenuOpen" class="navbar-menu mobile-menu">
          <router-link to="/" :class="{ active: route.name === 'topnews' }" @click="toggleMobileMenu">TopNews</router-link>
          <router-link to="/newnews" :class="{ active: route.name === 'newnews' }" @click="toggleMobileMenu">NewNews</router-link>
          <router-link to="/wall" :class="{ active: route.name === 'wall' }" @click="toggleMobileMenu">WallOfNews</router-link>
          <router-link to="/system" :class="{ active: route.name === 'system' }" @click="toggleMobileMenu">System</router-link>
          <router-link to="/settings" :class="{ active: route.name === 'settings' }" @click="toggleMobileMenu">Settings</router-link>
        </div>
      </div>
    </nav>

    <!-- Main content -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.navbar {
  background: var(--surface-color);
  border-bottom: 1px solid var(--border-color);
  padding: 0.75rem 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow);
}

.navbar-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-color);
  text-decoration: none;
}

.logo {
  height: 28px;
  width: auto;
  color: var(--text-color);
}

.logo-text {
  height: 20px;
  width: auto;
  color: var(--text-color);
}

.mobile-menu-btn {
  display: none;
  background: none;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  padding: 0.5rem;
}

.navbar-menu {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

@media (max-width: 768px) {
  .mobile-menu-btn {
    display: block;
  }

  .desktop-menu {
    display: none !important;
  }

  .mobile-menu {
    display: flex;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--surface-color);
    border-bottom: 1px solid var(--border-color);
    padding: 1rem;
    flex-direction: column;
    box-shadow: var(--shadow);
  }

  .mobile-menu a {
    padding: 0.75rem 1rem;
    display: block;
  }
}

@media (min-width: 769px) {
  .mobile-menu {
    display: none !important;
  }
}

.navbar-menu a {
  padding: 0.5rem 1rem;
  color: var(--text-muted);
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s ease;
  font-weight: 500;
}

.navbar-menu a:hover {
  color: var(--text-color);
  background-color: var(--bg-color);
}

.navbar-menu a.active {
  color: var(--text-color);
  background-color: var(--bg-color);
  font-weight: 600;
}

.theme-toggle {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  color: var(--text-color);
  background-color: var(--bg-color);
}

.main-content {
  flex: 1;
  padding: 2rem 0;
}

@media (max-width: 768px) {
  .main-content {
    padding: 1rem 0;
  }
}
</style>
