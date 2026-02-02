<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'

const loading = ref(true)
const error = ref(null)
const umapData = ref([])
const svgContainer = ref(null)
const tooltip = ref(null)

const fetchUmapData = async () => {
  try {
    loading.value = true
    error.value = null

    const response = await fetch('/api/news/umap')
    if (!response.ok) throw new Error('Failed to fetch UMAP data')

    umapData.value = await response.json()
    await nextTick()
    renderVisualization()

  } catch (err) {
    error.value = err.message
    console.error('Error fetching UMAP data:', err)
  } finally {
    loading.value = false
  }
}

// Helper function to safely extract hostname from URL
const getHostname = (url) => {
  if (!url) return 'Unknown source'
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

const renderVisualization = () => {
  if (!umapData.value || umapData.value.length === 0) return
  if (!svgContainer.value) return

  // Clear previous visualization
  d3.select(svgContainer.value).selectAll('*').remove()

  const data = umapData.value

  // Setup dimensions
  const width = svgContainer.value.clientWidth || 800
  const height = 600
  const margin = { top: 20, right: 140, bottom: 20, left: 20 }

  // Create scales
  const xExtent = d3.extent(data, d => d.x)
  const yExtent = d3.extent(data, d => d.y)
  const xPadding = (xExtent[1] - xExtent[0]) * 0.05
  const yPadding = (yExtent[1] - yExtent[0]) * 0.05

  const xScale = d3.scaleLinear()
    .domain([xExtent[0] - xPadding, xExtent[1] + xPadding])
    .range([margin.left, width - margin.right])

  const yScale = d3.scaleLinear()
    .domain([yExtent[0] - yPadding, yExtent[1] + yPadding])
    .range([height - margin.bottom, margin.top])

  // Create color scale for clusters
  const uniqueClusters = [...new Set(data.map(d => d.cluster_id))].filter(id => id !== undefined && id !== null)
  const colorScale = d3.scaleOrdinal()
    .domain(uniqueClusters)
    .range(d3.schemeCategory10)

  // Create SVG
  const svg = d3.select(svgContainer.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .style('background', 'var(--bg-color)')

  // Add points for news items
  svg.selectAll('circle')
    .data(data.filter(d => d.type === 'news_item'))
    .enter()
    .append('circle')
    .attr('cx', d => xScale(d.x))
    .attr('cy', d => yScale(d.y))
    .attr('r', 5)
    .attr('fill', d => d.cluster_id !== undefined && d.cluster_id !== null ?
      colorScale(d.cluster_id) : 'var(--text-muted)')
    .attr('opacity', d => d.opacity !== undefined ? d.opacity : 0.7)
    .style('cursor', 'pointer')
    .on('mouseover', function(event, d) {
      d3.select(this)
        .attr('r', 8)
        .attr('opacity', 1)

      if (tooltip.value) {
        tooltip.value.style.display = 'block'
        tooltip.value.style.left = (event.pageX + 10) + 'px'
        tooltip.value.style.top = (event.pageY + 10) + 'px'
        tooltip.value.querySelector('.tooltip-title').textContent = d.title || 'Untitled'
        tooltip.value.querySelector('.tooltip-source').textContent = getHostname(d.source_url)
        tooltip.value.querySelector('.tooltip-cluster').textContent = d.cluster_id !== undefined && d.cluster_id !== null ?
          `Cluster ${d.cluster_id}` : 'Unclustered'
      }
    })
    .on('mouseout', function(event, d) {
      d3.select(this)
        .attr('r', 5)
        .attr('opacity', d.opacity !== undefined ? d.opacity : 0.7)
      if (tooltip.value) {
        tooltip.value.style.display = 'none'
      }
    })
    .on('click', function(event, d) {
      if (d.url) {
        window.open(d.url, '_blank')
      }
    })

  // Add squares for preference vectors
  const squareSize = 10
  const prefVectors = data.filter(d => d.type === 'preference_vector')

  svg.selectAll('rect.pref-vector')
    .data(prefVectors)
    .enter()
    .append('rect')
    .attr('class', 'pref-vector')
    .attr('x', d => xScale(d.x) - squareSize / 2)
    .attr('y', d => yScale(d.y) - squareSize / 2)
    .attr('width', squareSize)
    .attr('height', squareSize)
    .attr('fill', 'var(--primary-color)')
    .attr('stroke', 'var(--surface-color)')
    .attr('stroke-width', 2)
    .style('cursor', 'pointer')
    .on('mouseover', function(event, d) {
      d3.select(this).attr('stroke-width', 3)

      if (tooltip.value) {
        tooltip.value.style.display = 'block'
        tooltip.value.style.left = (event.pageX + 10) + 'px'
        tooltip.value.style.top = (event.pageY + 10) + 'px'
        tooltip.value.querySelector('.tooltip-title').textContent = d.title || 'Preference Vector'
        tooltip.value.querySelector('.tooltip-source').textContent = 'Preference Vector'
        tooltip.value.querySelector('.tooltip-cluster').textContent = d.description || ''
      }
    })
    .on('mouseout', function() {
      d3.select(this).attr('stroke-width', 2)
      if (tooltip.value) {
        tooltip.value.style.display = 'none'
      }
    })

  // Add labels for preference vectors
  svg.selectAll('text.pref-label')
    .data(prefVectors)
    .enter()
    .append('text')
    .attr('class', 'pref-label')
    .attr('x', d => xScale(d.x) + squareSize)
    .attr('y', d => yScale(d.y) + squareSize / 2)
    .attr('fill', 'var(--text-color)')
    .attr('font-size', '12px')
    .text(d => d.title || '')

  // Add legend
  const legendSpacing = 20
  const legendCircleRadius = 5
  const legendTextOffset = 10
  const legend = svg.append('g')
    .attr('class', 'legend')
    .attr('transform', `translate(${width - 130}, ${margin.top})`)

  // Add cluster legend items
  if (uniqueClusters.length > 0) {
    const legendItems = legend.selectAll('.legend-item-cluster')
      .data(uniqueClusters)
      .enter()
      .append('g')
      .attr('class', 'legend-item-cluster')
      .attr('transform', (d, i) => `translate(0, ${i * legendSpacing})`)

    legendItems.append('circle')
      .attr('r', legendCircleRadius)
      .attr('fill', d => colorScale(d))

    legendItems.append('text')
      .attr('x', legendTextOffset)
      .attr('y', legendCircleRadius / 2)
      .attr('fill', 'var(--text-color)')
      .attr('font-size', '12px')
      .text(d => `Cluster ${d}`)
  }

  // Add unclustered legend item
  const unclusteredY = uniqueClusters.length * legendSpacing
  const unclusteredGroup = legend.append('g')
    .attr('transform', `translate(0, ${unclusteredY})`)

  unclusteredGroup.append('circle')
    .attr('r', legendCircleRadius)
    .attr('fill', 'var(--text-muted)')

  unclusteredGroup.append('text')
    .attr('x', legendTextOffset)
    .attr('y', legendCircleRadius / 2)
    .attr('fill', 'var(--text-color)')
    .attr('font-size', '12px')
    .text('Unclustered')

  // Add preference vector legend item
  const prefVectorY = (uniqueClusters.length + 1) * legendSpacing
  const prefGroup = legend.append('g')
    .attr('transform', `translate(0, ${prefVectorY})`)

  prefGroup.append('rect')
    .attr('x', -legendCircleRadius)
    .attr('y', -legendCircleRadius)
    .attr('width', legendCircleRadius * 2)
    .attr('height', legendCircleRadius * 2)
    .attr('fill', 'var(--primary-color)')
    .attr('stroke', 'var(--surface-color)')
    .attr('stroke-width', 1)

  prefGroup.append('text')
    .attr('x', legendTextOffset)
    .attr('y', legendCircleRadius / 2)
    .attr('fill', 'var(--text-color)')
    .attr('font-size', '12px')
    .text('Preference Vector')
}

// Handle window resize
let resizeTimeout
const handleResize = () => {
  clearTimeout(resizeTimeout)
  resizeTimeout = setTimeout(() => {
    if (umapData.value.length > 0) {
      renderVisualization()
    }
  }, 250)
}

onMounted(() => {
  fetchUmapData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
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
        <p>2D projection of news articles using UMAP dimensionality reduction. Colors represent different clusters, transparency indicates article age (newer = more opaque). Click on points to open articles.</p>
        <p class="mb-0"><strong>Data points:</strong> {{ umapData.length }}</p>
      </div>

      <div ref="svgContainer" class="svg-container">
        <!-- D3.js will render the SVG here -->
      </div>

      <!-- Tooltip -->
      <div ref="tooltip" class="tooltip-box">
        <div class="tooltip-title"></div>
        <div class="tooltip-source"></div>
        <div class="tooltip-cluster"></div>
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
  position: relative;
}

.info-box {
  margin-bottom: 1.5rem;
  padding: 1rem 1.5rem;
  background: var(--bg-color);
  border-radius: 6px;
}

.info-box p {
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 0.5rem;
  font-size: 0.9375rem;
}

.svg-container {
  background: var(--bg-color);
  border-radius: 6px;
  overflow: hidden;
  min-height: 600px;
}

.svg-container :deep(svg) {
  display: block;
  width: 100%;
}

.tooltip-box {
  display: none;
  position: fixed;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  box-shadow: var(--shadow-hover);
  z-index: 1000;
  pointer-events: none;
  max-width: 300px;
}

.tooltip-title {
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.25rem;
  line-height: 1.3;
}

.tooltip-source {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.tooltip-cluster {
  font-size: 0.8125rem;
  color: var(--primary-color);
  margin-top: 0.25rem;
}

@media (max-width: 768px) {
  .umap-header h1 {
    font-size: 1.5rem;
  }

  .visualization-container {
    padding: 1rem;
  }

  .svg-container {
    min-height: 400px;
  }
}
</style>
