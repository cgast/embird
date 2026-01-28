<script setup>
import { ref, onMounted } from 'vue'

const loading = ref(true)
const error = ref(null)
const umapData = ref([])
const svgElement = ref(null)

const fetchUmapData = async () => {
  try {
    loading.value = true
    error.value = null

    const response = await fetch('/api/news/umap')
    if (!response.ok) throw new Error('Failed to fetch UMAP data')

    umapData.value = await response.json()
    renderVisualization()

  } catch (err) {
    error.value = err.message
    console.error('Error fetching UMAP data:', err)
  } finally {
    loading.value = false
  }
}

const renderVisualization = () => {
  // This is a placeholder - in a real implementation, you would use D3.js here
  // For now, we'll create a simple SVG visualization
  if (!umapData.value || umapData.value.length === 0) return

  // Note: The actual UMAP visualization would require D3.js
  // This is a simplified version
  console.log('UMAP data loaded:', umapData.value.length, 'items')
}

onMounted(() => {
  fetchUmapData()
})
</script>

<template>
  <div class="container">
    <div class="umap-header">
      <h1>UMAP Visualization</h1>
      <p class="text-muted">2D visualization of news articles and preference vectors</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading visualization...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="alert">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Visualization -->
    <div v-else class="visualization-container">
      <div class="info-box">
        <h3>Visualization Info</h3>
        <p>This view shows a 2D projection of news articles and preference vectors using UMAP (Uniform Manifold Approximation and Projection).</p>
        <p class="mb-2"><strong>Data points:</strong> {{ umapData.length }}</p>
        <p class="text-muted">Note: Full D3.js visualization requires integration with the D3 library. The backend provides the data at /api/news/umap.</p>
      </div>

      <div ref="svgElement" class="svg-container">
        <svg width="100%" height="600" viewBox="0 0 800 600">
          <text x="400" y="300" text-anchor="middle" fill="var(--text-muted)">
            D3.js UMAP visualization would render here
          </text>
          <text x="400" y="330" text-anchor="middle" fill="var(--text-muted)" font-size="14">
            {{ umapData.length }} data points loaded
          </text>
        </svg>
      </div>

      <div class="legend">
        <h3>Legend</h3>
        <div class="legend-items">
          <div class="legend-item">
            <div class="legend-circle news"></div>
            <span>News Articles</span>
          </div>
          <div class="legend-item">
            <div class="legend-square preference"></div>
            <span>Preference Vectors</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.umap-header {
  margin-bottom: 2rem;
}

.umap-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.visualization-container {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 2rem;
  box-shadow: var(--shadow);
}

.info-box {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: var(--bg-color);
  border-radius: 6px;
}

.info-box h3 {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.info-box p {
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 0.5rem;
}

.svg-container {
  margin-bottom: 2rem;
  background: var(--bg-color);
  border-radius: 6px;
  overflow: hidden;
}

.svg-container svg {
  display: block;
}

.legend {
  padding: 1.5rem;
  background: var(--bg-color);
  border-radius: 6px;
}

.legend h3 {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--text-color);
}

.legend-items {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-circle,
.legend-square {
  width: 20px;
  height: 20px;
  border: 2px solid var(--primary-color);
}

.legend-circle {
  border-radius: 50%;
  background: var(--primary-color);
}

.legend-square {
  background: var(--secondary-color);
  border-color: var(--secondary-color);
}

@media (max-width: 768px) {
  .umap-header h1 {
    font-size: 1.5rem;
  }

  .visualization-container {
    padding: 1rem;
  }

  .svg-container svg {
    height: 400px;
  }
}
</style>
