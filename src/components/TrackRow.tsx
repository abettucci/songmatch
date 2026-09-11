import { ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface TrackRowData {
  spotify_id: string
  name: string
  artist: string
  album?: string
  album_image?: string
  external_url?: string
}

interface TrackRowProps {
  track: TrackRowData
  /** Optional right-aligned label, e.g. a formatted played_at time. */
  meta?: string
}

export function TrackRow({ track, meta }: TrackRowProps) {
  return (
    <div className="flex items-center gap-3 p-3 border border-border/30 rounded-lg hover:border-border/60 transition-colors bg-card/30">
      {track.album_image && (
        <img
          src={track.album_image}
          alt={track.album || track.name}
          className="w-12 h-12 rounded-md object-cover shadow-sm shrink-0"
        />
      )}
      <div className="flex-1 min-w-0">
        <h4 className="font-medium truncate text-sm">{track.name}</h4>
        <p className="text-xs text-muted-foreground truncate">{track.artist}</p>
      </div>
      {meta && <span className="text-xs text-muted-foreground shrink-0">{meta}</span>}
      {track.external_url && (
        <Button
          size="sm"
          variant="outline"
          className="shrink-0"
          onClick={() => window.open(track.external_url, '_blank')}
        >
          <ExternalLink className="w-4 h-4" />
        </Button>
      )}
    </div>
  )
}
