import { useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Search, Music, Loader2, Play, Pause } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

interface Song {
  spotify_id: string;
  name: string;
  artist: string;
  album: string;
  preview_url?: string;
  album_image?: string;
  external_url: string;
  popularity?: number;
}

interface SongSearchProps {
  onSongSelect: (song: Song) => void;
  selectedSongs: Song[];
}

export function SongSearch({ onSongSelect, selectedSongs }: SongSearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Song[]>([]);
  const [loading, setLoading] = useState(false);
  const [playingPreview, setPlayingPreview] = useState<string | null>(null);
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    const delaySearch = setTimeout(() => {
      if (query.trim().length > 2) {
        searchTracks();
      } else {
        setResults([]);
      }
    }, 500);

    return () => clearTimeout(delaySearch);
  }, [query]);

  useEffect(() => {
    // Cleanup audio on unmount
    return () => {
      if (audio) {
        audio.pause();
        audio.src = '';
      }
    };
  }, [audio]);

  const searchTracks = async () => {
    setLoading(true);
    try {
      const response = await apiClient.searchTracks(query, 20);
      setResults(response.tracks);
    } catch (error: any) {
      toast({
        title: 'Search failed',
        description: error.message || 'Please try again',
        variant: 'destructive',
      });
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const togglePreview = (previewUrl: string, trackId: string) => {
    if (playingPreview === trackId) {
      audio?.pause();
      setPlayingPreview(null);
    } else {
      if (audio) {
        audio.pause();
      }
      const newAudio = new Audio(previewUrl);
      newAudio.play();
      newAudio.onended = () => setPlayingPreview(null);
      setAudio(newAudio);
      setPlayingPreview(trackId);
    }
  };

  const isSelected = (trackId: string) => {
    return selectedSongs.some((s) => s.spotify_id === trackId);
  };

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-5 h-5" />
        <Input
          type="text"
          placeholder="Search for songs, artists, or albums..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-10 pr-4"
        />
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}

      {!loading && results.length === 0 && query.trim().length > 2 && (
        <div className="text-center py-8 text-muted-foreground">
          No results found for "{query}"
        </div>
      )}

      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {results.map((track) => (
          <Card
            key={track.spotify_id}
            className={`p-3 hover:bg-accent/50 transition-colors cursor-pointer ${
              isSelected(track.spotify_id) ? 'bg-primary/10 border-primary' : ''
            }`}
            onClick={() => {
              onSongSelect(track);
              setQuery('');
              setResults([]);
            }}
          >
            <div className="flex items-center gap-3">
              {track.album_image ? (
                <img
                  src={track.album_image}
                  alt={track.name}
                  className="w-12 h-12 rounded object-cover"
                />
              ) : (
                <div className="w-12 h-12 rounded bg-muted flex items-center justify-center">
                  <Music className="w-6 h-6 text-muted-foreground" />
                </div>
              )}

              <div className="flex-1 min-w-0">
                <div className="font-semibold truncate">{track.name}</div>
                <div className="text-sm text-muted-foreground truncate">
                  {track.artist}
                </div>
              </div>

              {track.preview_url && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePreview(track.preview_url!, track.spotify_id);
                  }}
                  className="shrink-0"
                >
                  {playingPreview === track.spotify_id ? (
                    <Pause className="w-4 h-4" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
