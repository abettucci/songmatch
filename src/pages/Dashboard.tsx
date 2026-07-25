import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { SongSearch } from '@/components/SongSearch'
import { RecommendationSettings } from '@/components/RecommendationSettings'
import { SongRecommendations } from '@/components/SongRecommendations'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import { LogOut, Music, X, Sparkles, Link, Link2Off } from 'lucide-react'

interface Song {
  spotify_id: string
  name: string
  artist: string
  album: string
  preview_url?: string
  album_image?: string
  external_url: string
  popularity?: number
}

interface PreferencesType {
  min_energy?: number
  max_energy?: number
  min_valence?: number
  max_valence?: number
  min_danceability?: number
  max_danceability?: number
  min_acousticness?: number
  max_acousticness?: number
  min_instrumentalness?: number
  max_instrumentalness?: number
  min_liveness?: number
  max_liveness?: number
  min_speechiness?: number
  max_speechiness?: number
  min_tempo?: number
  max_tempo?: number
  min_loudness?: number
  max_loudness?: number
  genre_weight?: number
  spectral_analysis?: boolean
  algorithm?: 'lastfm' | 'custom' | 'audio' | 'structural' | 'clap'
  market?: string
  use_filters?: boolean
  enabled_filters?: {
    energy?: boolean
    valence?: boolean
    danceability?: boolean
    acousticness?: boolean
    instrumentalness?: boolean
    liveness?: boolean
    speechiness?: boolean
    tempo?: boolean
    loudness?: boolean
    genre?: boolean
  }
}

export default function Dashboard() {
  const { user, signOut } = useAuth()
  const { toast } = useToast()
  const [selectedSongs, setSelectedSongs] = useState<Song[]>([])
  const [recommendations, setRecommendations] = useState<Song[]>([])
  const [preferences, setPreferences] = useState<PreferencesType>({
    market: 'US',
    genre_weight: 0.7,
    spectral_analysis: true
  })
  const [loading, setLoading] = useState(false)
  const [spotifyLoading, setSpotifyLoading] = useState(false)

  const handleSongSelect = (song: Song) => {
    if (selectedSongs.length >= 5) {
      toast({
        title: "Maximum songs selected",
        description: "You can select up to 5 songs as seeds",
        variant: "destructive"
      })
      return
    }

    if (!selectedSongs.some(s => s.spotify_id === song.spotify_id)) {
      setSelectedSongs([...selectedSongs, song])
      toast({
        title: "Song added",
        description: `${song.name} by ${song.artist} added to your seeds`
      })
    }
  }

  const removeSong = (songId: string) => {
    setSelectedSongs(selectedSongs.filter(s => s.spotify_id !== songId))
  }

  const getRecommendations = async () => {
    if (selectedSongs.length === 0) {
      toast({
        title: "No seed songs",
        description: "Please select at least one song to get recommendations",
        variant: "destructive"
      })
      return
    }

    setLoading(true)
    try {
      const seedTracks = selectedSongs.map(s => s.spotify_id)
      
      const result = await apiClient.getRecommendations({
        seed_tracks: seedTracks,
        algorithm: preferences.algorithm || 'lastfm',
        limit: 10,
        filters: preferences.use_filters !== false ? preferences : null,
      })
      
      setRecommendations(result.recommendations || [])

      toast({
        title: "Recommendations generated!",
        description: `Found ${result.recommendations?.length || 0} similar songs using ${result.algorithm_used}`
      })
    } catch (error: any) {
      toast({
        title: "Failed to get recommendations",
        description: error.message || "Please try again",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSignOut = async () => {
    await signOut()
  }

  const handleConnectSpotify = async () => {
    setSpotifyLoading(true)
    try {
      const { auth_url } = await apiClient.getSpotifyAuthUrl()
      window.location.href = auth_url
    } catch (error: any) {
      toast({
        title: "Failed to connect Spotify",
        description: error.message || "Please try again",
        variant: "destructive"
      })
      setSpotifyLoading(false)
    }
  }

  const handleDisconnectSpotify = async () => {
    setSpotifyLoading(true)
    try {
      await apiClient.disconnectSpotify()
      toast({ title: "Spotify disconnected" })
      // Reload user to update spotify_connected
      window.location.reload()
    } catch (error: any) {
      toast({
        title: "Failed to disconnect",
        description: error.message || "Please try again",
        variant: "destructive"
      })
    } finally {
      setSpotifyLoading(false)
    }
  }

  const handleUseTopTracks = async () => {
    setSpotifyLoading(true)
    try {
      const { tracks } = await apiClient.getSpotifyTopTracks()
      const topFive = tracks.slice(0, 5)
      setSelectedSongs(topFive)
      toast({
        title: "Top tracks loaded",
        description: `Added your top ${topFive.length} Spotify tracks as seeds`
      })
    } catch (error: any) {
      toast({
        title: "Failed to load top tracks",
        description: error.message || "Please try again",
        variant: "destructive"
      })
    } finally {
      setSpotifyLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/10 via-secondary/10 to-accent/10">
      {/* Header */}
      <header className="bg-card/80 backdrop-blur-sm border-b border-border/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-primary to-secondary rounded-lg flex items-center justify-center">
                <Music className="w-5 h-5 text-primary-foreground" />
              </div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                SoundMatch
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground hidden sm:block">
                Welcome, {user?.email}
              </span>

              {/* Spotify connect/disconnect */}
              {user?.spotify_connected ? (
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30 gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
                    Spotify
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleUseTopTracks}
                    disabled={spotifyLoading}
                    className="text-green-400 hover:text-green-300 hover:bg-green-500/10 text-xs h-8 px-2"
                  >
                    Use my top tracks
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDisconnectSpotify}
                    disabled={spotifyLoading}
                    className="text-muted-foreground hover:text-destructive h-8 w-8 p-0"
                    title="Disconnect Spotify"
                  >
                    <Link2Off className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleConnectSpotify}
                  disabled={spotifyLoading}
                  className="border-green-500/40 text-green-400 hover:bg-green-500/10 gap-2"
                >
                  <Link className="w-4 h-4" />
                  Connect Spotify
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={handleSignOut}
                className="border-border/50"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column - Song Search & Selected Songs */}
          <div className="lg:col-span-2 space-y-6">
            {/* Song Search */}
            <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
              <CardHeader>
                <CardTitle>Search for Songs</CardTitle>
              </CardHeader>
              <CardContent>
                <SongSearch 
                  onSongSelect={handleSongSelect}
                  selectedSongs={selectedSongs}
                />
              </CardContent>
            </Card>

            {/* Selected Songs */}
            {selectedSongs.length > 0 && (
              <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Seed Songs ({selectedSongs.length}/5)</CardTitle>
                    <Button 
                      onClick={getRecommendations}
                      disabled={loading || selectedSongs.length === 0}
                      className="bg-gradient-to-r from-primary to-secondary hover:from-primary/90 hover:to-secondary/90"
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      Get Recommendations
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {selectedSongs.map((song) => (
                      <Badge 
                        key={song.spotify_id} 
                        variant="secondary" 
                        className="flex items-center gap-2 py-2 px-3 bg-gradient-to-r from-secondary/20 to-accent/20 border border-border/30"
                      >
                        <span className="truncate max-w-48">
                          {song.name} - {song.artist}
                        </span>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => removeSong(song.spotify_id)}
                          className="h-4 w-4 p-0 hover:bg-destructive/20"
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recommendations */}
            <SongRecommendations 
              recommendations={recommendations}
              loading={loading}
            />
          </div>

          {/* Right Column - Settings */}
          <div className="space-y-6">
            <RecommendationSettings 
              preferences={preferences}
              onPreferencesChange={setPreferences}
            />
          </div>
        </div>
      </div>
    </div>
  )
}