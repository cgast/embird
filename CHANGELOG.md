# Changelog

## [0.3.0] - 2026-02-25

### Features
- vue interface, new architecture and deployment workflow (03ffa0c)
- implement light/dark theme toggle with localStorage persistence (f7f1aa0)
- add health check endpoint and docker healthchecks (c92f00f)
- add preference vectors toggle and fix interval calculation (471f3cf)
- implement dynamic nginx proxy configuration (10460f8)
- use EmBird logo as favicon and update title (b44841a)
- add keyword-based cluster naming (2710d98)
- add hierarchical subclusters for large clusters (2b18df1)
- improve clusters page readability with expandable cards (dabb2f7)

### Bug Fixes
- include devDependencies in Docker build (f60818e)
- improve nginx healthchecks and dns resolution (355f119)
- correct make_interval parameter order in trending endpoint (7d02e01)
- fix mobile nav and news page double fetch (96d3b55)
- fix missing parameters in visualization functions and improve dashboard stats styling (24ca2eb)
- use helper function for URL domain extraction in NewsList (96f24a2)
- implement D3.js UMAP visualization with error handling (0ac9927)
- add required 'type' field to source creation form (1bbd6ab)
- regenerate package-lock.json to fix npm ci build failure (3279b33)
- implement recursive hierarchical subclustering (7f67c9d)
- show all registered sources in filters and track crawl status (16bd6a8)
- fix multiple bugs preventing new sources from being crawled (5d9eb3d)

### Documentation
- add mobile app feasibility report and architecture assessment (c2dba72)

### Styling
- update application branding and favicon assets (41d0085)

### Other
- Update logo to new bird + text SVG and convert to monochrome UI (ef8fbba)
- Refactor top menu and add WallOfNews view (ce74de6)
- Refactor article detail view: compact layout, vector-similar articles (a50925c)
- Refactor article detail view: compact layout, vector-similar articles (8de4610)
- Sort articles newest-first on the cluster view homepage (a5fd99b)
- Fix UMAP visualization: tooltips, repaint, cluster names (ff50402)
- Fix UMAP visualization: loader, cluster names, and top-20 filtering (2db87ca)
- Fix UMAP visualization to load immediately instead of on scroll (d186d36)
- Add working login to settings page with auth-gated editing (f00562b)
- Reorganize pages: combine News+Search into Archive, Preferences+Sources into Settings (0a4462d)
- Redesign homepage, dashboard, and article pages (76d09d1)
- Update README.md (e49e76f)
- repo renamed (f0f6041)
- port removed for parallel use in coolify (ce1b47f)
- renamed to EmBird (5e2936d)
- fixed display (6e80969)
