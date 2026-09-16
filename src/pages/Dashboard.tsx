import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { SongSearch } from '@/components/SongSearch'
import { RecommendationSettings } from '@/components/RecommendationSettings'
import { SongRecommendations } from '@/components/SongRecommendations'
import { RecentlyPlayed } from '@/components/RecentlyPlayed'
import { ListeningHistoryByDay } from '@/components/ListeningHistoryByDay'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useToast } from '@/hooks/use-toast'
import { apiClient, type SpotifyPlaylistGenreCreation, type SpotifyPlaylistGenrePreview, type SpotifyPlaylistGenreTrack } from '@/lib/api-client'
import { Loader2, LogOut, Music, X, Sparkles, Link, Link2Off, ListMusic, ChevronDown, ExternalLink } from 'lucide-react'

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

const SPOTIFY_PLAYLIST_ID_PATTERN = /^[A-Za-z0-9]{22}$/

function extractSpotifyPlaylistId(input: string): string | null {
  const value = input.trim()
  if (SPOTIFY_PLAYLIST_ID_PATTERN.test(value)) return value

  if (value.startsWith('spotify:playlist:')) {
    const id = value.slice('spotify:playlist:'.length)
    return SPOTIFY_PLAYLIST_ID_PATTERN.test(id) ? id : null
  }

  try {
    const url = new URL(value)
    if (url.hostname !== 'open.spotify.com') return null
    const [, resource, id] = url.pathname.split('/')
    return resource === 'playlist' && SPOTIFY_PLAYLIST_ID_PATTERN.test(id) ? id : null
  } catch {
    return null
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback
}

function representativeTrackIds(tracks: SpotifyPlaylistGenreTrack[], maximum = 5): string[] {
  const uniqueIds = [...new Set(tracks.map((track) => track.spotify_id).filter(Boolean))]
  if (uniqueIds.length <= maximum) return uniqueIds

  // Spread the seeds through the source order so long playlists do not only
  // represent their first few songs.
  return Array.from({ length: maximum }, (_, index) => uniqueIds[Math.floor(index * uniqueIds.length / maximum)])
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
  const [playlistInput, setPlaylistInput] = useState('')
  const [genrePreview, setGenrePreview] = useState<SpotifyPlaylistGenrePreview | null>(null)
  const [selectedGenre, setSelectedGenre] = useState('')
  const [genreLoading, setGenreLoading] = useState(false)
  const [confirmGenrePlaylist, setConfirmGenrePlaylist] = useState(false)
  const [createdGenrePlaylist, setCreatedGenrePlaylist] = useState<SpotifyPlaylistGenreCreation | null>(null)

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

  const handlePreviewPlaylistGenres = async () => {
    const playlistId = extractSpotifyPlaylistId(playlistInput)
    if (!playlistId) {
      toast({
        title: 'Invalid playlist link',
        description: 'Paste a Spotify playlist link, URI, or its 22-character ID.',
        variant: 'destructive',
      })
      return
    }

    setGenreLoading(true)
    setGenrePreview(null)
    setSelectedGenre('')
    setCreatedGenrePlaylist(null)
    try {
      const preview = await apiClient.previewSpotifyPlaylistGenres(playlistId)
      setGenrePreview(preview)
      if (preview.genres.length === 0) {
        toast({
          title: 'No genre metadata found',
          description: 'Spotify did not return genres for the artists in this playlist.',
          variant: 'destructive',
        })
      }
    } catch (error: unknown) {
      toast({
        title: 'Could not analyze playlist',
        description: getErrorMessage(error, 'Please reconnect Spotify and try again.'),
        variant: 'destructive',
      })
    } finally {
      setGenreLoading(false)
    }
  }

  const handleCreateGenrePlaylist = async () => {
    if (!genrePreview || !selectedGenre) return

    setGenreLoading(true)
    try {
      const created = await apiClient.createSpotifyGenrePlaylist(
        genrePreview.playlist_id,
        selectedGenre,
        genrePreview.confirmation_token,
      )
      setCreatedGenrePlaylist(created)
      setConfirmGenrePlaylist(false)
      toast({
        title: 'Playlist created in Spotify',
        description: `${created.track_count} ${created.genre} tracks were added.`,
      })
    } catch (error: unknown) {
      toast({
        title: 'Could not create playlist',
        description: getErrorMessage(error, 'Please try again.'),
        variant: 'destructive',
      })
    } finally {
      setGenreLoading(false)
    }
  }

  const handlePlaylistRecommendations = async (tracks: SpotifyPlaylistGenreTrack[], source: string) => {
    const seedTracks = representativeTrackIds(tracks)
    if (seedTracks.length === 0) {
      toast({
        title: 'No songs available',
        description: 'This category does not have playable Spotify tracks to use as seeds.',
        variant: 'destructive',
      })
      return
    }

    setLoading(true)
    try {
      const result = await apiClient.getRecommendations({
        seed_tracks: seedTracks,
        algorithm: preferences.algorithm || 'lastfm',
        limit: 10,
        filters: preferences.use_filters !== false ? preferences : null,
      })
      setRecommendations(result.recommendations || [])
      toast({
        title: 'Recommendations ready',
        description: `${result.recommendations?.length || 0} songs inspired by ${source}.`,
      })
    } catch (error: unknown) {
      toast({
        title: 'Could not generate recommendations',
        description: getErrorMessage(error, 'Please try again.'),
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
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

            {user?.spotify_connected && (
              <>
                <RecentlyPlayed />
                <ListeningHistoryByDay />
              </>
            )}
          </div>

          {/* Right Column - Settings */}
          <div className="space-y-6">
            <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ListMusic className="h-5 w-5 text-green-400" />
                  Organize a Spotify playlist
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Analyze the genres of every credited artist, then create a new private playlist for one genre.
                </p>
                {!user?.spotify_connected ? (
                  <Button onClick={handleConnectSpotify} disabled={spotifyLoading} className="w-full gap-2">
                    <Link className="h-4 w-4" />
                    Connect Spotify first
                  </Button>
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="spotify-playlist">Playlist link or ID</Label>
                      <Input
                        id="spotify-playlist"
                        value={playlistInput}
                        onChange={(event) => setPlaylistInput(event.target.value)}
                        placeholder="https://open.spotify.com/playlist/..."
                        autoComplete="off"
                      />
                    </div>
                    <Button
                      onClick={handlePreviewPlaylistGenres}
                      disabled={genreLoading || !playlistInput.trim()}
                      className="w-full"
                    >
                      {genreLoading && !genrePreview ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ListMusic className="mr-2 h-4 w-4" />}
                      Analyze genres
                    </Button>
                    <Button
                      variant="link"
                      size="sm"
                      onClick={handleConnectSpotify}
                      disabled={spotifyLoading}
                      className="h-auto w-full p-0 text-green-400"
                    >
                      Reconnect Spotify to grant playlist permissions
                    </Button>

                    {genrePreview && (
                      <div className="space-y-3 rounded-lg border border-border/50 bg-background/40 p-3">
                        <div>
                          <p className="font-medium leading-tight">{genrePreview.playlist_name}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {genrePreview.total_tracks} tracks · {genrePreview.genres.length} genres found · Review every category before creating a playlist.
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          onClick={() => handlePlaylistRecommendations(
                            genrePreview.tracks,
                            `the style of ${genrePreview.playlist_name}`,
                          )}
                          disabled={loading || genreLoading || genrePreview.tracks.length === 0}
                          className="w-full"
                        >
                          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                          Recommend from playlist style
                        </Button>
                        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Songs in each category</p>
                          {genrePreview.genre_tracks.map((group) => (
                            <details key={group.name} className="group rounded-md border border-border/45 bg-card/40">
                              <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-sm font-medium marker:hidden">
                                <span className="truncate">{group.name} <span className="text-muted-foreground">({group.track_count})</span></span>
                                <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" />
                              </summary>
                              <div className="space-y-2 border-t border-border/35 px-3 py-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-full justify-start px-0 text-xs text-primary hover:text-primary"
                                  onClick={() => handlePlaylistRecommendations(group.tracks, `the ${group.name} group`)}
                                  disabled={loading || genreLoading || group.tracks.length === 0}
                                >
                                  <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                                  Recommend from this genre
                                </Button>
                                <ul className="space-y-1.5">
                                  {group.tracks.map((track) => (
                                    <li key={track.spotify_id} className="flex items-center justify-between gap-2 text-xs">
                                      <span className="min-w-0 truncate"><span className="font-medium">{track.name}</span><span className="text-muted-foreground"> · {track.artist}</span></span>
                                      {track.external_url && (
                                        <a href={track.external_url} target="_blank" rel="noreferrer" aria-label={`Open ${track.name} in Spotify`} className="text-muted-foreground hover:text-primary">
                                          <ExternalLink className="h-3.5 w-3.5" />
                                        </a>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </details>
                          ))}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="genre-select">Genre to export</Label>
                          <Select value={selectedGenre} onValueChange={setSelectedGenre}>
                            <SelectTrigger id="genre-select">
                              <SelectValue placeholder="Choose a genre" />
                            </SelectTrigger>
                            <SelectContent>
                              {genrePreview.genres.map((genre) => (
                                <SelectItem key={genre.name} value={genre.name}>
                                  {genre.name} ({genre.track_count})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <Button
                          onClick={() => setConfirmGenrePlaylist(true)}
                          disabled={!selectedGenre || genreLoading}
                          className="w-full bg-green-600 hover:bg-green-700"
                        >
                          Create private playlist
                        </Button>
                        {selectedGenre && (
                          <Button
                            variant="secondary"
                            onClick={() => {
                              const group = genrePreview.genre_tracks.find((item) => item.name === selectedGenre)
                              if (group) handlePlaylistRecommendations(group.tracks, `the ${selectedGenre} group`)
                            }}
                            disabled={loading || genreLoading}
                            className="w-full"
                          >
                            <Sparkles className="mr-2 h-4 w-4" />
                            Recommend from selected genre
                          </Button>
                        )}
                      </div>
                    )}

                    {createdGenrePlaylist?.playlist_url && (
                      <Button asChild variant="outline" className="w-full">
                        <a href={createdGenrePlaylist.playlist_url} target="_blank" rel="noreferrer">
                          Open {createdGenrePlaylist.playlist_name}
                        </a>
                      </Button>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            <RecommendationSettings 
              preferences={preferences}
              onPreferencesChange={setPreferences}
            />
          </div>
        </div>
      </div>

      <AlertDialog open={confirmGenrePlaylist} onOpenChange={setConfirmGenrePlaylist}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Create a Spotify playlist?</AlertDialogTitle>
            <AlertDialogDescription>
              {genrePreview && selectedGenre
                ? `SoundMatch will create a new private playlist containing the ${selectedGenre} tracks from ${genrePreview.playlist_name}. Your source playlist will not be changed.`
                : 'Your source playlist will not be changed.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={genreLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleCreateGenrePlaylist} disabled={genreLoading}>
              {genreLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Confirm and create
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
