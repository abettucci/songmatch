import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, Heart, Save, Sparkles } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { apiClient, APIError } from '@/lib/api-client'

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

interface SongRecommendationsProps {
  recommendations: Song[]
  loading: boolean
}

export function SongRecommendations({ recommendations, loading }: SongRecommendationsProps) {
  const [likedSongs, setLikedSongs] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  const handleLike = (songId: string) => {
    const newLikedSongs = new Set(likedSongs)
    if (likedSongs.has(songId)) {
      newLikedSongs.delete(songId)
      toast({
        title: "Removed from favorites",
        description: "Song removed from your favorites"
      })
    } else {
      newLikedSongs.add(songId)
      toast({
        title: "Added to favorites",
        description: "Song added to your favorites"
      })
    }
    setLikedSongs(newLikedSongs)
  }

  const handleSavePlaylist = async () => {
    if (recommendations.length === 0) return

    setSaving(true)
    try {
      const name = `Recommendations ${new Date().toLocaleDateString()}`
      const trackIds = recommendations.map(s => s.spotify_id)
      await apiClient.savePlaylist(name, trackIds)
      toast({
        title: "Playlist saved!",
        description: `Saved ${recommendations.length} tracks to "${name}"`
      })
    } catch (error: any) {
      if (error instanceof APIError && error.status === 401) {
        toast({
          title: "Sign in required",
          description: "Please sign in to save playlists",
          variant: "destructive"
        })
      } else {
        toast({
          title: "Save failed",
          description: error.message || "Please try again",
          variant: "destructive"
        })
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 animate-pulse" />
            Generating Recommendations...
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4 border border-border/30 rounded-lg animate-pulse">
                <div className="w-16 h-16 bg-muted rounded-md" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-muted rounded w-3/4" />
                  <div className="h-3 bg-muted/70 rounded w-1/2" />
                  <div className="h-3 bg-muted/50 rounded w-1/3" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (recommendations.length === 0) {
    return (
      <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="text-center py-12">
          <Sparkles className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No recommendations yet</h3>
          <p className="text-muted-foreground">Add some seed songs to get personalized recommendations!</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5" />
            Recommendations ({recommendations.length})
          </CardTitle>
          <Button
            onClick={handleSavePlaylist}
            disabled={saving}
            size="sm"
            className="bg-gradient-to-r from-secondary to-accent hover:from-secondary/90 hover:to-accent/90"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Save Playlist'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {recommendations.map((song) => (
            <div key={song.spotify_id} className="flex items-center gap-4 p-4 border border-border/30 rounded-lg hover:border-border/60 transition-colors bg-card/30">
              {song.album_image && (
                <img
                  src={song.album_image}
                  alt={song.album}
                  className="w-16 h-16 rounded-md object-cover shadow-sm"
                />
              )}
              <div className="flex-1 min-w-0">
                <h3 className="font-medium truncate">{song.name}</h3>
                <p className="text-sm text-muted-foreground truncate">{song.artist}</p>
                <p className="text-xs text-muted-foreground truncate">{song.album}</p>
                <div className="flex items-center gap-2 mt-1">
                  {song.popularity && (
                    <Badge variant="secondary" className="text-xs">
                      {song.popularity}% popular
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {song.preview_url && (
                  <audio controls className="w-32 h-8">
                    <source src={song.preview_url} type="audio/mpeg" />
                  </audio>
                )}
                <Button
                  size="sm"
                  variant={likedSongs.has(song.spotify_id) ? "default" : "outline"}
                  onClick={() => handleLike(song.spotify_id)}
                  className={likedSongs.has(song.spotify_id) ? "bg-red-500 hover:bg-red-600 text-white" : ""}
                >
                  <Heart className={`w-4 h-4 ${likedSongs.has(song.spotify_id) ? 'fill-current' : ''}`} />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(song.external_url, '_blank')}
                >
                  <ExternalLink className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
