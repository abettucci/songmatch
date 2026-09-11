import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { History } from 'lucide-react'
import { apiClient, type SpotifyTrackPlayed } from '@/lib/api-client'
import { TrackRow } from '@/components/TrackRow'

function formatPlayedAt(playedAt: string): string {
  return new Date(playedAt).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function RecentlyPlayed() {
  const [tracks, setTracks] = useState<SpotifyTrackPlayed[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiClient
      .getSpotifyRecentlyPlayed(20)
      .then((response) => {
        if (!cancelled) setTracks(response.tracks)
      })
      .catch(() => {
        if (!cancelled) setTracks([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="w-5 h-5 animate-pulse" />
            Recently played
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 p-3 border border-border/30 rounded-lg animate-pulse">
                <div className="w-12 h-12 bg-muted rounded-md" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-muted rounded w-2/3" />
                  <div className="h-3 bg-muted/70 rounded w-1/3" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (tracks.length === 0) {
    return (
      <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="text-center py-12">
          <History className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No recently played tracks</h3>
          <p className="text-muted-foreground">Play something on Spotify and it'll show up here.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="w-5 h-5 text-green-400" />
          Recently played
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {tracks.map((track, index) => (
            <TrackRow key={`${track.spotify_id}-${track.played_at}-${index}`} track={track} meta={formatPlayedAt(track.played_at)} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
