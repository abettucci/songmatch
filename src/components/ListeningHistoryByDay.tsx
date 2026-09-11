import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { CalendarDays } from 'lucide-react'
import { apiClient, type SpotifyListeningHistoryDay } from '@/lib/api-client'
import { TrackRow } from '@/components/TrackRow'

function formatDay(dateIso: string): string {
  const date = new Date(`${dateIso}T00:00:00Z`)
  return date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', timeZone: 'UTC' })
}

export function ListeningHistoryByDay() {
  const [days, setDays] = useState<SpotifyListeningHistoryDay[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiClient
      .getSpotifyListeningHistory(7)
      .then((response) => {
        if (!cancelled) setDays(response.days)
      })
      .catch(() => {
        if (!cancelled) setDays([])
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
            <CalendarDays className="w-5 h-5 animate-pulse" />
            Listening history
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (days.length === 0) {
    return (
      <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="text-center py-12">
          <CalendarDays className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No listening history yet</h3>
          <p className="text-muted-foreground">
            History builds up daily once your Spotify account is connected — check back tomorrow.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarDays className="w-5 h-5 text-green-400" />
          Listening history
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible defaultValue={days[0]?.date}>
          {days.map((day) => (
            <AccordionItem key={day.date} value={day.date}>
              <AccordionTrigger>
                <div className="flex items-center gap-2">
                  <span>{formatDay(day.date)}</span>
                  <Badge variant="secondary" className="text-xs">
                    {day.total_tracks} {day.total_tracks === 1 ? 'track' : 'tracks'}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-4">
                  {day.genres.map((genre) => (
                    <div key={genre.name} className="space-y-2">
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {genre.name} · {genre.tracks.length}
                      </p>
                      <div className="space-y-2">
                        {genre.tracks.map((track, index) => (
                          <TrackRow key={`${track.spotify_id}-${track.played_at}-${index}`} track={track} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  )
}
