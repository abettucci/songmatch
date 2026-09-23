// API Client for SoundMatch Backend

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

export interface SpotifyPlaylistGenre {
  name: string;
  track_count: number;
}

export interface SpotifyPlaylistGenreTrack {
  spotify_id: string;
  name: string;
  artist: string;
  album?: string;
  album_image?: string;
  external_url?: string;
}

export interface SpotifyPlaylistGenreTrackGroup extends SpotifyPlaylistGenre {
  tracks: SpotifyPlaylistGenreTrack[];
}

export interface SpotifyPlaylistGenrePreview {
  playlist_id: string;
  playlist_name: string;
  total_tracks: number;
  categorized_tracks: number;
  tracks: SpotifyPlaylistGenreTrack[];
  genres: SpotifyPlaylistGenre[];
  genre_tracks: SpotifyPlaylistGenreTrackGroup[];
  confirmation_token: string;
}

export interface SpotifyPlaylistGenreCreation {
  playlist_id: string;
  playlist_name: string;
  playlist_url: string;
  genre: string;
  track_count: number;
}

export interface SpotifyTrackPlayed {
  spotify_id: string;
  name: string;
  artist: string;
  album?: string;
  album_image?: string;
  external_url?: string;
  played_at: string;
}

export interface SpotifyTrackLiked extends Omit<SpotifyTrackPlayed, 'played_at'> {
  added_at: string;
}

export interface SpotifyLikedTracksGenreGroup {
  name: string;
  tracks: SpotifyTrackLiked[];
}

export interface SpotifyListeningHistoryGenreGroup {
  name: string;
  tracks: SpotifyTrackPlayed[];
}

export interface SpotifyListeningHistoryDay {
  date: string;
  genres: SpotifyListeningHistoryGenreGroup[];
  total_tracks: number;
}

export interface CompanionProfile {
  user_id: string;
  display_name: string;
  bio: string;
  city: string;
  public_interests: string[];
  visible: boolean;
  music_affinity_consent: boolean;
  adult_confirmed: boolean;
}

export interface CompanionConcert {
  id: string;
  artist: string;
  venue: string;
  city: string;
  starts_at: string;
  status: 'scheduled' | 'cancelled' | 'completed';
  attending: boolean;
}

export interface CompanionCandidate {
  user_id: string;
  display_name: string;
  bio: string;
  city: string;
  public_interests: string[];
  affinity_score: number;
  affinity_level: 'alto' | 'medio' | 'bajo';
  affinity_reasons: string[];
}

export interface CompanionMatch {
  id: string;
  concert: CompanionConcert;
  companion: CompanionCandidate;
  created_at: string;
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

  async previewSpotifyPlaylistGenres(playlistId: string): Promise<SpotifyPlaylistGenrePreview> {
    return this.request<SpotifyPlaylistGenrePreview>('/api/v1/spotify/playlist-genres/preview', {
      method: 'POST',
      body: JSON.stringify({ playlist_id: playlistId }),
    });
  }

  async createSpotifyGenrePlaylist(
    playlistId: string,
    genre: string,
    confirmationToken: string,
  ): Promise<SpotifyPlaylistGenreCreation> {
    return this.request<SpotifyPlaylistGenreCreation>('/api/v1/spotify/playlist-genres/create', {
      method: 'POST',
      body: JSON.stringify({
        playlist_id: playlistId,
        genre,
        confirmation_token: confirmationToken,
      }),
    });
  }

  async getSpotifyRecentlyPlayed(limit: number = 20): Promise<{ tracks: SpotifyTrackPlayed[] }> {
    return this.request<{ tracks: SpotifyTrackPlayed[] }>(
      `/api/v1/spotify/recently-played?limit=${limit}`,
      { method: 'GET' },
    );
  }

  async getSpotifyLikedTracks(limit: number = 20): Promise<{ tracks: SpotifyTrackLiked[]; genres: SpotifyLikedTracksGenreGroup[] }> {
    return this.request<{ tracks: SpotifyTrackLiked[]; genres: SpotifyLikedTracksGenreGroup[] }>(
      `/api/v1/spotify/liked-tracks?limit=${limit}`,
      { method: 'GET' },
    );
  }

  async getSpotifyListeningHistory(days: number = 7): Promise<{ days: SpotifyListeningHistoryDay[] }> {
    return this.request<{ days: SpotifyListeningHistoryDay[] }>(
      `/api/v1/spotify/listening-history?days=${days}`,
      { method: 'GET' },
    );
  }

  async getCompanionProfile(): Promise<CompanionProfile> {
    return this.request<CompanionProfile>('/api/v1/companions/profile', { method: 'GET' });
  }

  async saveCompanionProfile(profile: Omit<CompanionProfile, 'user_id'>): Promise<CompanionProfile> {
    return this.request<CompanionProfile>('/api/v1/companions/profile', { method: 'PUT', body: JSON.stringify(profile) });
  }

  async getCompanionConcerts(): Promise<CompanionConcert[]> {
    return this.request<CompanionConcert[]>('/api/v1/companions/concerts', { method: 'GET' });
  }

  async createCompanionConcert(concert: Omit<CompanionConcert, 'id' | 'attending'>): Promise<CompanionConcert> {
    return this.request<CompanionConcert>('/api/v1/companions/concerts', { method: 'POST', body: JSON.stringify(concert) });
  }

  async setCompanionAttendance(concertId: string, status: 'active' | 'withdrawn'): Promise<void> {
    await this.request(`/api/v1/companions/concerts/${concertId}/attendance`, { method: 'POST', body: JSON.stringify({ status }) });
  }

  async getCompanionCandidates(concertId: string): Promise<{ concert: CompanionConcert; candidates: CompanionCandidate[] }> {
    return this.request(`/api/v1/companions/concerts/${concertId}/candidates`, { method: 'GET' });
  }

  async swipeCompanion(concertId: string, targetUserId: string, action: 'pass' | 'interested'): Promise<{ matched: boolean; match_id?: string }> {
    return this.request(`/api/v1/companions/concerts/${concertId}/swipes`, { method: 'POST', body: JSON.stringify({ target_user_id: targetUserId, action }) });
  }

  async getCompanionMatches(): Promise<{ matches: CompanionMatch[] }> {
    return this.request('/api/v1/companions/matches', { method: 'GET' });
  }

  async blockCompanion(userId: string): Promise<void> {
    await this.request('/api/v1/companions/blocks', { method: 'POST', body: JSON.stringify({ user_id: userId }) });
  }

  async reportCompanion(userId: string, reason: 'safety' | 'harassment' | 'spam' | 'other', note = ''): Promise<void> {
    await this.request('/api/v1/companions/reports', { method: 'POST', body: JSON.stringify({ user_id: userId, reason, note }) });
  }

  // Health check
  async healthCheck() {
    return this.request<{ status: string }>('/health', { method: 'GET' });
  }
}

// Export singleton instance
export const apiClient = new APIClient(API_URL);
export { APIError };
