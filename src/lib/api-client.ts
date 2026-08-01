// API Client for SoundMatch Backend

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

class APIClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new APIError(response.status, error.detail || error.error || 'Request failed');
    }

    return response.json();
  }

  // Authentication
  async register(email: string, password: string) {
    const response = await this.request<{ user: any; token: string }>(
      '/api/v1/auth/register',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }
    );
    this.setToken(response.token);
    return response;
  }

  async login(email: string, password: string) {
    const response = await this.request<{ user: any; token: string }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }
    );
    this.setToken(response.token);
    return response;
  }

  async logout() {
    try {
      await this.request('/api/v1/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  }

  async getCurrentUser() {
    return this.request<{ id: string; email: string }>('/api/v1/auth/me', {
      method: 'GET',
    });
  }

  // Search
  async searchTracks(query: string, limit: number = 20) {
    return this.request<{ tracks: any[] }>('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    });
  }

  // Recommendations
  async getRecommendations(params: {
    seed_tracks: string[];
    algorithm?: string;
    limit?: number;
    filters?: any;
  }) {
    return this.request<{
      recommendations: any[];
      method: string;
      algorithm_used: string;
    }>('/api/v1/recommendations', {
      method: 'POST',
      body: JSON.stringify({
        seed_tracks: params.seed_tracks,
        algorithm: params.algorithm || 'lastfm',
        limit: params.limit || 20,
        filters: params.filters || null,
      }),
    });
  }

  // Audio Features
  async getAudioFeatures(previewUrls: string[]) {
    return this.request<{ audio_features: any[] }>('/api/v1/audio-features', {
      method: 'POST',
      body: JSON.stringify({ preview_urls: previewUrls }),
    });
  }

  // Playlists
  async savePlaylist(name: string, tracks: string[]) {
    return this.request('/api/v1/playlists', {
      method: 'POST',
      body: JSON.stringify({ name, tracks }),
    });
  }

  async getUserPlaylists() {
    return this.request<{ playlists: any[] }>('/api/v1/playlists', {
      method: 'GET',
    });
  }

  // Spotify OAuth
  async getSpotifyAuthUrl(): Promise<{ auth_url: string }> {
    return this.request<{ auth_url: string }>('/api/v1/auth/spotify/login', {
      method: 'GET',
    });
  }

  async disconnectSpotify(): Promise<void> {
    await this.request('/api/v1/auth/spotify/disconnect', { method: 'DELETE' });
  }

  async getSpotifyTopTracks(): Promise<{ tracks: any[] }> {
    return this.request<{ tracks: any[] }>('/api/v1/auth/spotify/top-tracks', {
      method: 'GET',
    });
  }

  // Health check
  async healthCheck() {
    return this.request<{ status: string }>('/health', { method: 'GET' });
  }
}

// Export singleton instance
export const apiClient = new APIClient(API_URL);
export { APIError };

