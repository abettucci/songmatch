import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Heart, ChevronDown, ListMusic, RefreshCw } from 'lucide-react'
import { apiClient, type SpotifyLikedTracksGenreGroup, type SpotifyTrackLiked } from '@/lib/api-client'
import { TrackRow } from '@/components/TrackRow'

function formatAddedAt(addedAt: string): string {
  return new Date(addedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function LikedTracksPlaylist() {
  const [tracks, setTracks] = useState<SpotifyTrackLiked[]>([])
  const [genres, setGenres] = useState<SpotifyLikedTracksGenreGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [openGenres, setOpenGenres] = useState<Set<string>>(new Set())

  const loadPlaylist = async () => {
    setLoading(true)
    try {
      const response = await apiClient.getSpotifyLikedTracks(20)
      setTracks(response.tracks)
      setGenres(response.genres)
      setOpenGenres(new Set(response.genres.slice(0, 1).map((group) => group.name)))
    } catch {
      setTracks([])
      setGenres([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadPlaylist()
  }, [])

  const genreSummary = useMemo(
    () => genres.slice(0, 3).map((group) => `${group.name} · ${group.tracks.length}`).join('   '),
    [genres],
  )

  const toggleGenre = (genre: string) => {
    setOpenGenres((previous) => {
      const next = new Set(previous)
      if (next.has(genre)) next.delete(genre)
      else next.add(genre)
      return next
    })
  }

  return (
    <Card className="overflow-hidden border border-rose-400/20 bg-card/70 shadow-[0_18px_60px_-32px_hsl(350_85%_55%/0.55)] backdrop-blur-sm">
      <div className="h-1 bg-gradient-to-r from-rose-500 via-pink-400 to-amber-300" />
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <CardTitle className="flex items-center gap-2">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-rose-500/15 text-rose-500">
                <Heart className="h-4 w-4 fill-current" />
              </span>
              Mi playlist de likes
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Tus 20 canciones guardadas más recientes, organizadas acá mismo.
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={loadPlaylist} disabled={loading} aria-label="Actualizar canciones liked">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        {!loading && tracks.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-2 text-xs text-muted-foreground">
            <Badge variant="secondary" className="gap-1 bg-rose-500/10 text-rose-600 dark:text-rose-300">
              <ListMusic className="h-3 w-3" /> {tracks.length} canciones
            </Badge>
            <span className="hidden sm:inline">{genreSummary}</span>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {[...Array(4)].map((_, index) => <div key={index} className="h-16 animate-pulse rounded-lg bg-muted/70" />)}
          </div>
        ) : tracks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 px-5 py-10 text-center">
            <Heart className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <p className="font-medium">No encontramos canciones guardadas</p>
            <p className="mt-1 text-sm text-muted-foreground">Guardá música con el corazón en Spotify y volvé a actualizar esta lista.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {genres.map((group) => {
              const isOpen = openGenres.has(group.name)
              return (
                <Collapsible key={group.name} open={isOpen} onOpenChange={() => toggleGenre(group.name)}>
                  <div className="rounded-xl border border-border/50 bg-background/35 transition-colors hover:border-rose-400/35">
                    <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold capitalize">{group.name}</span>
                        <span className="text-xs text-muted-foreground">{group.tracks.length} {group.tracks.length === 1 ? 'canción' : 'canciones'}</span>
                      </span>
                      <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${isOpen ? '' : '-rotate-90'}`} />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-2 border-t border-border/40 px-2.5 py-2.5">
                      {group.tracks.map((track) => (
                        <TrackRow key={track.spotify_id} track={track} meta={`Guardada ${formatAddedAt(track.added_at)}`} />
                      ))}
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
