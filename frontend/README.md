# EmBird Frontend

Modern, responsive Vue.js frontend for the EmBird news aggregation system.

## Features

- **Modern Stack**: Vue 3 + Vite for fast development and optimal production builds
- **Responsive Design**: Mobile-first design that works on all screen sizes
- **Dark/Light Theme**: Toggle between light and dark themes with localStorage persistence
- **Semantic Search**: Search news by meaning, not just keywords
- **News Clustering**: View semantically similar articles grouped together
- **UMAP Visualization**: 2D visualization of news articles and preference vectors
- **Preference Vectors**: Manage custom preference vectors to influence news scoring
- **RSS Management**: Add and manage news sources

## Technology Stack

- **Vue 3** - Progressive JavaScript framework
- **Vue Router** - Official router for Vue.js
- **Vite** - Next generation frontend tooling
- **CSS Variables** - For theming support
- **Fetch API** - For API communication

## Project Structure

```
frontend/
├── public/                # Static assets
│   └── EmBird-logo.png   # Application logo
├── src/
│   ├── components/        # Reusable Vue components
│   │   └── NewsCard.vue  # News article card component
│   ├── views/            # Page components
│   │   ├── Dashboard.vue        # Main dashboard
│   │   ├── NewsList.vue         # All news list
│   │   ├── NewsDetail.vue       # Single article view
│   │   ├── NewsClusters.vue     # Clustered news view
│   │   ├── Search.vue           # Semantic search
│   │   ├── UmapVisual.vue       # UMAP visualization
│   │   ├── PreferenceVectors.vue # Vector management
│   │   └── Sources.vue          # RSS source management
│   ├── App.vue           # Root component with navigation
│   ├── main.js           # Application entry point
│   └── style.css         # Global styles and theme
├── index.html            # HTML entry point
├── vite.config.js        # Vite configuration
└── package.json          # Dependencies and scripts
```

## Development

### Prerequisites

- Node.js 18+
- npm or yarn
- EmBird backend running on `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Running Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Building for Production

```bash
npm run build
```

Built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## API Integration

The frontend communicates with the backend API through Vite's proxy configuration. All requests to `/api/*` are proxied to `http://localhost:8000`.

### Key API Endpoints

- `GET /api/news` - Get all news articles
- `GET /api/news/{id}` - Get single news article
- `GET /api/news/search?query=...` - Semantic search
- `GET /api/news/clusters` - Get clustered news
- `GET /api/news/umap` - Get UMAP visualization data
- `GET /api/news/trending` - Get trending news
- `GET /api/preference-vectors` - Get preference vectors
- `POST /api/preference-vectors` - Create preference vector
- `PUT /api/preference-vectors/{id}` - Update preference vector
- `DELETE /api/preference-vectors/{id}` - Delete preference vector
- `GET /api/urls` - Get RSS sources
- `POST /api/urls` - Add RSS source
- `DELETE /api/urls/{id}` - Delete RSS source

## Theme System

The application supports light and dark themes using CSS variables. Theme preference is stored in localStorage.

### CSS Variables

```css
:root {
  --primary-color: #4a7ba7;      /* Main brand color */
  --bg-color: #f8f9fa;           /* Background color */
  --surface-color: #ffffff;      /* Card/surface color */
  --text-color: #212529;         /* Main text color */
  --text-muted: #6c757d;         /* Muted text color */
  --border-color: #dee2e6;       /* Border color */
  --shadow: 0 2px 8px rgba(...); /* Box shadow */
}
```

## Responsive Breakpoints

- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

## Components

### NewsCard

Reusable component for displaying news articles.

**Props:**
- `newsItem` (Object, required) - News article data
- `showSimilarity` (Boolean, default: false) - Show similarity score

### Views

Each view is a standalone page component:

- **Dashboard**: Shows trending news from last 24 hours with stats
- **NewsList**: Paginated list with source filtering
- **NewsDetail**: Full article view with related news
- **NewsClusters**: Articles grouped by semantic similarity
- **Search**: Semantic search interface
- **UmapVisual**: 2D UMAP visualization
- **PreferenceVectors**: CRUD interface for preference vectors
- **Sources**: Manage RSS feed URLs

## Deployment

### Static Hosting

Build the app and deploy the `dist/` directory to any static hosting service:

```bash
npm run build
# Deploy dist/ to Vercel, Netlify, Cloudflare Pages, etc.
```

### Backend Integration

For production, configure the Vite proxy or use environment variables to point to your production API.

```js
// vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: process.env.API_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

Same as EmBird backend
