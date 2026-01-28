<script setup>
import { ref, onMounted } from 'vue'

const vectors = ref([])
const loading = ref(true)
const error = ref(null)
const showAddForm = ref(false)
const editingId = ref(null)

const newVector = ref({
  title: '',
  description: ''
})

const fetchVectors = async () => {
  try {
    loading.value = true
    error.value = null

    // Note: This endpoint would need to be added to the API
    const response = await fetch('/api/preference-vectors')
    if (!response.ok) {
      throw new Error('Failed to fetch preference vectors')
    }

    vectors.value = await response.json()

  } catch (err) {
    error.value = err.message
    console.error('Error fetching vectors:', err)
  } finally {
    loading.value = false
  }
}

const createVector = async () => {
  if (!newVector.value.title || !newVector.value.description) {
    error.value = 'Title and description are required'
    return
  }

  try {
    const response = await fetch('/api/preference-vectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newVector.value)
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || 'Failed to create vector')
    }

    newVector.value = { title: '', description: '' }
    showAddForm.value = false
    await fetchVectors()

  } catch (err) {
    error.value = err.message
  }
}

const deleteVector = async (id) => {
  if (!confirm('Are you sure you want to delete this vector?')) return

  try {
    const response = await fetch(`/api/preference-vectors/${id}`, {
      method: 'DELETE'
    })

    if (!response.ok) throw new Error('Failed to delete vector')

    await fetchVectors()

  } catch (err) {
    error.value = err.message
  }
}

const startEdit = (vector) => {
  editingId.value = vector.id
}

const cancelEdit = () => {
  editingId.value = null
}

const saveEdit = async (vector) => {
  try {
    const response = await fetch(`/api/preference-vectors/${vector.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: vector.title,
        description: vector.description
      })
    })

    if (!response.ok) throw new Error('Failed to update vector')

    editingId.value = null
    await fetchVectors()

  } catch (err) {
    error.value = err.message
  }
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

onMounted(() => {
  fetchVectors()
})
</script>

<template>
  <div class="container">
    <div class="vectors-header">
      <h1>Preference Vectors</h1>
      <p class="text-muted">Create and manage preference vectors to influence news scoring and visualization</p>
    </div>

    <!-- Error alert -->
    <div v-if="error" class="alert mb-3">
      <strong>Error:</strong> {{ error }}
      <button @click="error = null" class="btn btn-sm btn-outline" style="float: right;">Dismiss</button>
    </div>

    <!-- Add new vector -->
    <div class="card mb-4">
      <div class="card-header">
        <h2>Add New Preference Vector</h2>
        <button v-if="!showAddForm" @click="showAddForm = true" class="btn btn-primary">
          + Add Vector
        </button>
      </div>
      <div v-if="showAddForm" class="card-body">
        <form @submit.prevent="createVector">
          <div class="form-group mb-3">
            <label>Title</label>
            <input v-model="newVector.title" type="text" placeholder="Enter title" required />
          </div>
          <div class="form-group mb-3">
            <label>Description</label>
            <textarea v-model="newVector.description" rows="4"
                      placeholder="Enter text to generate vector from" required></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Create Vector</button>
            <button type="button" @click="showAddForm = false; newVector = { title: '', description: '' }"
                    class="btn btn-outline">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p class="text-muted">Loading vectors...</p>
    </div>

    <!-- Vectors list -->
    <div v-else-if="vectors.length > 0" class="vectors-list">
      <div class="card">
        <div class="card-header">
          <h2>Existing Preference Vectors</h2>
        </div>
        <div class="vectors-table">
          <div v-for="vector in vectors" :key="vector.id" class="vector-row">
            <template v-if="editingId === vector.id">
              <div class="vector-edit-form">
                <div class="form-group">
                  <label>Title</label>
                  <input v-model="vector.title" type="text" required />
                </div>
                <div class="form-group">
                  <label>Description</label>
                  <textarea v-model="vector.description" rows="4" required></textarea>
                </div>
                <div class="form-actions">
                  <button @click="saveEdit(vector)" class="btn btn-primary btn-sm">Save</button>
                  <button @click="cancelEdit" class="btn btn-outline btn-sm">Cancel</button>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="vector-content">
                <h3>{{ vector.title }}</h3>
                <p class="vector-description">{{ vector.description }}</p>
                <p class="text-muted vector-date">Created: {{ formatDate(vector.created_at) }}</p>
              </div>
              <div class="vector-actions">
                <button @click="startEdit(vector)" class="btn btn-sm btn-outline">Edit</button>
                <button @click="deleteVector(vector.id)" class="btn btn-sm btn-outline">Delete</button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="empty-state">
      <p class="text-muted">No preference vectors found. Add one using the form above.</p>
    </div>
  </div>
</template>

<style scoped>
.vectors-header {
  margin-bottom: 2rem;
}

.vectors-header h1 {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.card-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.card-body {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-color);
}

.form-actions {
  display: flex;
  gap: 1rem;
}

.loading-container {
  text-align: center;
  padding: 3rem 0;
}

.empty-state {
  text-align: center;
  padding: 3rem 0;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.vectors-table {
  display: flex;
  flex-direction: column;
}

.vector-row {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.vector-row:last-child {
  border-bottom: none;
}

.vector-content {
  flex: 1;
}

.vector-content h3 {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-color);
}

.vector-description {
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  max-width: 600px;
}

.vector-date {
  font-size: 0.875rem;
}

.vector-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.vector-edit-form {
  width: 100%;
  padding: 1rem;
  background: var(--bg-color);
  border-radius: 6px;
}

@media (max-width: 768px) {
  .vectors-header h1 {
    font-size: 1.5rem;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .vector-row {
    flex-direction: column;
  }

  .vector-actions {
    width: 100%;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions .btn {
    width: 100%;
  }
}
</style>
