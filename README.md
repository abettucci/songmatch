# Music Recommendation System

A sophisticated music recommendation platform built with React, TypeScript, Python (FastAPI), and AWS Lambda, featuring multiple recommendation algorithms and **advanced structural audio analysis** based on academic research.

## Architecture Overview

This application implements a comprehensive music recommendation system with multiple algorithms:

1. **Last.fm Algorithm** - Collaborative filtering based on user listening patterns
2. **Custom Algorithm** - Audio features analysis using Spotify API and librosa
3. **Audio Analysis Algorithm** - Deep audio feature extraction using librosa (tempo, energy, MFCCs, etc.)
4. **Structural Analysis Algorithm** - Advanced pattern recognition using Self-Similarity Matrices, Novelty Detection, and Hierarchical Clustering

### Structural Analysis (Based on Academic Research)

The structural analysis algorithm implements the methodology from **"Detección de estructuras musicales utilizando análisis de señales y representaciones visuales"** (Martínez, 2023):

#### Mathematical Foundations

1. **Self-Similarity Matrix (SSM)**
   - Compares each audio frame against all others using cosine similarity
   - Generated from both spectrogram (instrumental changes) and chromagram (harmonic changes)
   - Formula: `SSM[i,j] = similarity(feature_vector[i], feature_vector[j])`

2. **Novelty Score (Foote's Method)**
   - Detects section boundaries using a checkerboard kernel convolved along the SSM diagonal
   - Kernel includes Gaussian taper for smooth boundary detection
   - High novelty peaks indicate transitions between sections

3. **Section Detection**
   - Boundaries identified from novelty curve peaks
   - Minimum section duration enforced (default: 2 seconds)
   - Sections labeled with timing information

4. **Hierarchical Agglomerative Clustering**
   - Groups similar sections using Ward linkage with Euclidean distance
   - Optimal cluster count determined by Silhouette score
   - Assigns labels (A, B, C...) to identify verse, chorus, bridge, etc.

#### Audio Feature Extraction Pipeline

```
Audio File → Waveform → STFT → Spectrogram → Mel Spectrogram
                              → Chromagram (12 pitch classes)
                              → MFCCs (timbral features)
                              → Harmonic/Percussive separation
                              → Onset detection → Tempo/Beats
```

#### Extracted Features

| Category | Features |
|----------|----------|
| **Time-domain** | Waveform, RMS energy, Zero-crossing rate |
| **Frequency-domain** | Spectrogram, Mel spectrogram, Spectral centroid/rolloff/bandwidth/contrast/flatness |
| **Harmonic** | Chromagram (STFT, CQT, CENS), Tonnetz, Harmonic/Percussive ratio |
| **Rhythmic** | Tempo, Beat frames, Onset envelope, Tempogram |
| **Timbral** | MFCCs (13 coefficients) |
| **Derived** | Danceability, Valence, Acousticness, Instrumentalness, Speechiness, Liveness |

### ¿Por qué Last.fm para Collaborative Filtering?

**Limitaciones de la API de Spotify:**
La API de Spotify **no proporciona acceso a datos de comportamiento de usuarios** ni a funciones de collaborative filtering:

- ❌ No hay endpoints para ver el historial de reproducción de otros usuarios
- ❌ No hay endpoints para ver qué canciones escuchan usuarios similares
- ❌ El endpoint de recomendaciones (`/recommendations`) fue **deprecado** y ya no está disponible
- ❌ Los endpoints de audio features (`/audio-features`) y audio analysis (`/audio-analysis`) fueron **deprecados**
- ✅ Solo se puede acceder a búsqueda de canciones, información de tracks, álbumes y artistas

**Por qué Last.fm es la solución:**
Last.fm es una plataforma de scrobbling con **más de 100 millones de usuarios** que rastrea los hábitos de escucha:

- ✅ **Collaborative Filtering Real**: Analiza patrones de millones de usuarios que escuchan música similar
- ✅ **API Pública Gratuita**: Proporciona endpoints de similitud basados en comportamiento colectivo
- ✅ **Datos de Co-ocurrencia**: Si muchos usuarios que escuchan la canción A también escuchan la canción B, Last.fm detecta esta correlación
- ✅ **Score de Similitud**: Cada recomendación viene con un score de similitud basado en datos reales de usuarios
- ✅ **Metadatos Enriquecidos**: Información de géneros, tags, biografías de artistas

**¿Qué es Collaborative Filtering?**
El collaborative filtering (filtrado colaborativo) es una técnica que predice los intereses de un usuario basándose en las preferencias de muchos otros usuarios. En este caso:

1. **Usuario A** escucha las canciones X, Y, Z
2. **Usuario B** escucha las canciones X, Y, W
3. **Usuario C** escucha las canciones Y, Z, W
4. El sistema detecta que si te gusta X e Y, probablemente te gustará Z y W
5. **No requiere análisis de audio**, solo patrones de comportamiento

**Fuentes de Datos Utilizadas:**

| Fuente | Propósito | Algoritmo |
|--------|-----------|-----------|
| **Last.fm API** | Collaborative filtering, similitud de tracks y artistas | Last.fm |
| **Freesound API** | Análisis de textura de audio y timbre | Custom, Structural |
| **Spotify Web API** | Búsqueda de tracks, metadatos, popularidad | Todos |
| **Análisis Sintético** | Estimación de features basada en géneros | Custom, Structural |
| **Análisis Estructural** | Patrones de verso/coro, complejidad armónica/rítmica | Structural |

### Core Components

#### Frontend Components

##### `SongSearch` (`src/components/SongSearch.tsx`)
- **Purpose**: Search interface for finding and selecting seed tracks
- **Features**: 
  - Real-time Spotify search integration
  - Audio preview functionality
  - Visual feedback for selected tracks
  - Keyboard navigation support
- **Data Source**: Spotify Web API via backend API

##### `SongRecommendations` (`src/components/SongRecommendations.tsx`)
- **Purpose**: Display and interact with recommended tracks
- **Features**:
  - Audio preview controls
  - Like/favorite functionality with local state management
  - External Spotify links
  - Popularity indicators
  - Playlist saving functionality
  - Loading states with skeleton UI
- **State Management**: Local React state for user interactions

##### `RecommendationSettings` (`src/components/RecommendationSettings.tsx`)
- **Purpose**: Advanced configuration panel for recommendation algorithms
- **Audio Features Control**:
  - Energy Level (0-1): Controls track intensity from calm to energetic
  - Valence (0-1): Mood spectrum from sad to happy
  - Danceability (0-1): How suitable a track is for dancing
  - Acousticness (0-1): Electric vs acoustic instrumentation
  - Instrumentalness (0-1): Vocal vs instrumental content
  - Liveness (0-1): Studio vs live recording detection
  - Speechiness (0-1): Music vs speech-like content
  - Tempo (60-200 BPM): Track speed in beats per minute
  - Loudness (-60-0 dB): Track volume levels
  - Genre Matching Weight (0-1): Diversity vs genre consistency
- **Algorithm Selection**: Switch between Last.fm, Custom, and Structural algorithms
- **Market Selection**: Regional content availability

#### Backend API Endpoints

##### `POST /api/v1/search`
- **Purpose**: Secure Spotify Web API integration for track search
- **Authentication**: Uses client credentials flow with stored secrets
- **Features**: 
  - Query sanitization and validation
  - Result formatting and image optimization
  - Error handling and fallback mechanisms

##### `POST /api/v1/audio-features`
- **Purpose**: Alternative audio analysis since Spotify's audio features API is deprecated
- **Data Sources**:
  - **Freesound API**: For audio texture and timbre analysis
  - **Synthetic Analysis**: Genre-based feature estimation
  - **Last.fm API**: Artist and track metadata enrichment
- **Features Provided**:
  - Acousticness, danceability, energy, instrumentalness
  - Liveness, loudness, speechiness, tempo, valence
  - Custom spectral and harmonic analysis

##### `POST /api/v1/recommendations`
- **Purpose**: Core recommendation engine with multiple algorithm implementations

### Data Flow

1. **User Input**: Selects seed tracks via SongSearch component
2. **Configuration**: Adjusts preferences via RecommendationSettings
3. **Processing**: Selected algorithm processes seeds with user preferences
4. **Analysis**: Audio features and/or structural analysis performed
5. **Filtering**: Applied rules (genre weight, artist diversity, market constraints)
6. **Ranking**: Similarity scoring and final recommendation ranking
7. **Display**: Results shown via SongRecommendations component

### Security & Performance

- **API Keys**: Securely stored in environment variables
- **CORS**: Properly configured for web application access
- **Rate Limiting**: Built-in throttling for external API calls
- **Error Handling**: Comprehensive fallback mechanisms
- **Caching**: Optimized to minimize redundant API calls
- **Batch Processing**: Efficient handling of multiple track analysis

### Hard Rules Applied Across All Algorithms

1. **No Same Artist**: Prevents recommending tracks by artists already in seed selection
2. **Genre Filtering**: Respects user's genre weight preferences
3. **Market Availability**: Only recommends tracks available in selected market
4. **Duplicate Prevention**: Ensures no duplicate tracks in results
5. **Quality Thresholds**: Filters out tracks below minimum audio quality standards

## Technologies Used

- **Frontend**: React, TypeScript, Vite, Tailwind CSS, shadcn-ui
- **Backend**: Python 3.11, FastAPI, Uvicorn, Mangum (Lambda adapter)
- **Database**: PostgreSQL (Neon) with asyncpg/SQLAlchemy
- **Audio Processing**: librosa, numpy, scipy, scikit-learn
- **Visualization**: matplotlib
- **APIs**: Spotify Web API, Last.fm API
- **Authentication**: JWT (python-jose, passlib)
- **Infrastructure**: Terraform, GitHub Actions CI/CD, Docker
- **Deployment**: AWS Lambda + Netlify

## API Endpoints

### Structural Analysis Endpoints

#### `POST /api/v1/analyze-structure`
Performs complete structural analysis on an audio track.

**Request:**
```json
{
  "preview_url": "https://p.scdn.co/mp3-preview/..."
}
```

**Response:**
```json
{
  "duration": 30.0,
  "tempo": 120.5,
  "n_sections": 4,
  "n_clusters": 2,
  "silhouette_score": 0.65,
  "structure_pattern": "ABAB",
  "sections": [
    {
      "start_time": 0.0,
      "end_time": 7.5,
      "duration": 7.5,
      "cluster_id": 0,
      "label": "A",
      "loudness": 0.45
    }
  ],
  "stats": {
    "tempo": 120.5,
    "energy_mean": 0.72,
    "danceability": 0.85,
    "valence": 0.65
  }
}
```

#### `POST /api/v1/visualize-structure`
Generates visualizations for music structure analysis.

**Request:**
```json
{
  "preview_url": "https://p.scdn.co/mp3-preview/...",
  "include_combined": true,
  "include_ssm": true,
  "include_novelty": true,
  "include_structure": true
}
```

**Response:**
```json
{
  "combined": "base64-encoded-png...",
  "ssm": "base64-encoded-png...",
  "novelty": "base64-encoded-png...",
  "structure": "base64-encoded-png...",
  "structure_pattern": "ABAB",
  "n_sections": 4
}
```

### Recommendation Algorithms

#### `POST /api/v1/recommendations`

**Algorithms available:**
- `lastfm` - Collaborative filtering via Last.fm
- `custom` - Content-based using Spotify audio features
- `audio` - Deep audio analysis with librosa
- `structural` - Structural similarity using SSM and section patterns

**Request:**
```json
{
  "seed_tracks": ["spotify_track_id_1", "spotify_track_id_2"],
  "algorithm": "structural",
  "limit": 20
}
```

## Local Development

```sh
# Clone and setup
git clone <YOUR_GIT_URL>
cd <YOUR_PROJECT_NAME>

# Install frontend dependencies
npm install

# Start frontend dev server
npm run dev

# In another terminal, setup backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Run backend
python run.py
```

### Using Docker

```sh
cd backend
docker-compose up --build
```

## Project Structure

```
songmatch/
├── src/                          # Frontend React application
│   ├── components/               # UI components
│   └── ...
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py         # API endpoints
│   │   │   └── schemas.py        # Pydantic models
│   │   ├── core/
│   │   │   ├── config.py         # Settings management
│   │   │   └── security.py       # JWT authentication
│   │   ├── db/
│   │   │   ├── database.py       # Async PostgreSQL
│   │   │   ├── models.py         # SQLAlchemy models
│   │   │   └── repository.py     # Data access layer
│   │   └── services/
│   │       ├── audio_features.py # Comprehensive feature extraction
│   │       ├── audio_analysis.py # Unified analysis service
│   │       ├── structural_analysis.py # SSM, novelty, clustering
│   │       ├── visualization.py  # matplotlib visualizations
│   │       ├── spotify.py        # Spotify API client
│   │       ├── lastfm.py         # Last.fm API client
│   │       └── recommendations.py # Recommendation engine
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
└── README.md
```

## Deployment

The project uses GitHub Actions for automated deployment:
- Push to `main` branch triggers automatic deployment
- Backend deploys to AWS Lambda (via Mangum adapter)
- Frontend deploys to Netlify

## References

- Martínez, L. S. (2023). "Detección de estructuras musicales utilizando análisis de señales y representaciones visuales"
- Foote, J. (2000). "Automatic audio segmentation using a measure of audio novelty"
- McFee, B., et al. (2015). "librosa: Audio and Music Signal Analysis in Python"

## Custom Domain

Navigate to Netlify → Domain Settings to connect your custom domain.
