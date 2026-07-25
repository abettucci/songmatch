import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import { Settings } from 'lucide-react'

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

interface RecommendationSettingsProps {
  preferences: PreferencesType
  onPreferencesChange: (preferences: PreferencesType) => void
}

export function RecommendationSettings({ preferences, onPreferencesChange }: RecommendationSettingsProps) {
  const updatePreference = (key: keyof PreferencesType, value: any) => {
    onPreferencesChange({
      ...preferences,
      [key]: value
    })
  }

  const toggleFilter = (filterKey: string, enabled: boolean) => {
    const currentFilters = preferences.enabled_filters || {}
    onPreferencesChange({
      ...preferences,
      enabled_filters: {
        ...currentFilters,
        [filterKey]: enabled
      }
    })
  }

  const useFilters = preferences.use_filters !== false
  const enabledFilters = preferences.enabled_filters || {}

  const energyRange = [preferences.min_energy || 0, preferences.max_energy || 1]
  const valenceRange = [preferences.min_valence || 0, preferences.max_valence || 1]
  const danceabilityRange = [preferences.min_danceability || 0, preferences.max_danceability || 1]
  const acousticnessRange = [preferences.min_acousticness || 0, preferences.max_acousticness || 1]
  const instrumentalnessRange = [preferences.min_instrumentalness || 0, preferences.max_instrumentalness || 1]
  const livenessRange = [preferences.min_liveness || 0, preferences.max_liveness || 1]
  const speechinessRange = [preferences.min_speechiness || 0, preferences.max_speechiness || 1]
  const tempoRange = [preferences.min_tempo || 60, preferences.max_tempo || 200]
  const loudnessRange = [preferences.min_loudness || -60, preferences.max_loudness || 0]

  return (
    <Card className="border border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Settings className="w-5 h-5" />
          Recommendation Settings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between space-x-2 p-4 bg-muted/50 rounded-lg">
          <div className="space-y-0.5">
            <Label className="text-sm font-medium">Use Audio Feature Filters</Label>
            <p className="text-xs text-muted-foreground">
              {useFilters ? 'Using selected filters to refine recommendations' : 'Using only algorithm without filters'}
            </p>
          </div>
          <Switch
            checked={useFilters}
            onCheckedChange={(checked) => updatePreference('use_filters', checked)}
          />
        </div>

        {useFilters && (
          <>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Energy Level</Label>
                <Checkbox
                  checked={enabledFilters.energy !== false}
                  onCheckedChange={(checked) => toggleFilter('energy', checked as boolean)}
                />
              </div>
              <Slider
                value={energyRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_energy', min)
                  updatePreference('max_energy', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.energy === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Calm ({energyRange[0].toFixed(1)})</span>
                <span>Energetic ({energyRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Mood (Valence)</Label>
                <Checkbox
                  checked={enabledFilters.valence !== false}
                  onCheckedChange={(checked) => toggleFilter('valence', checked as boolean)}
                />
              </div>
              <Slider
                value={valenceRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_valence', min)
                  updatePreference('max_valence', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.valence === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Sad ({valenceRange[0].toFixed(1)})</span>
                <span>Happy ({valenceRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Danceability</Label>
                <Checkbox
                  checked={enabledFilters.danceability !== false}
                  onCheckedChange={(checked) => toggleFilter('danceability', checked as boolean)}
                />
              </div>
              <Slider
                value={danceabilityRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_danceability', min)
                  updatePreference('max_danceability', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.danceability === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Not Danceable ({danceabilityRange[0].toFixed(1)})</span>
                <span>Very Danceable ({danceabilityRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Acousticness</Label>
                <Checkbox
                  checked={enabledFilters.acousticness !== false}
                  onCheckedChange={(checked) => toggleFilter('acousticness', checked as boolean)}
                />
              </div>
              <Slider
                value={acousticnessRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_acousticness', min)
                  updatePreference('max_acousticness', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.acousticness === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Electric ({acousticnessRange[0].toFixed(1)})</span>
                <span>Acoustic ({acousticnessRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Instrumentalness</Label>
                <Checkbox
                  checked={enabledFilters.instrumentalness !== false}
                  onCheckedChange={(checked) => toggleFilter('instrumentalness', checked as boolean)}
                />
              </div>
              <Slider
                value={instrumentalnessRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_instrumentalness', min)
                  updatePreference('max_instrumentalness', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.instrumentalness === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Vocal ({instrumentalnessRange[0].toFixed(1)})</span>
                <span>Instrumental ({instrumentalnessRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Liveness</Label>
                <Checkbox
                  checked={enabledFilters.liveness !== false}
                  onCheckedChange={(checked) => toggleFilter('liveness', checked as boolean)}
                />
              </div>
              <Slider
                value={livenessRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_liveness', min)
                  updatePreference('max_liveness', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.liveness === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Studio ({livenessRange[0].toFixed(1)})</span>
                <span>Live ({livenessRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Speechiness</Label>
                <Checkbox
                  checked={enabledFilters.speechiness !== false}
                  onCheckedChange={(checked) => toggleFilter('speechiness', checked as boolean)}
                />
              </div>
              <Slider
                value={speechinessRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_speechiness', min)
                  updatePreference('max_speechiness', max)
                }}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.speechiness === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Music ({speechinessRange[0].toFixed(1)})</span>
                <span>Speech-like ({speechinessRange[1].toFixed(1)})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Tempo (BPM)</Label>
                <Checkbox
                  checked={enabledFilters.tempo !== false}
                  onCheckedChange={(checked) => toggleFilter('tempo', checked as boolean)}
                />
              </div>
              <Slider
                value={tempoRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_tempo', min)
                  updatePreference('max_tempo', max)
                }}
                max={200}
                min={60}
                step={5}
                className="w-full"
                disabled={enabledFilters.tempo === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Slow ({tempoRange[0]})</span>
                <span>Fast ({tempoRange[1]})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Loudness (dB)</Label>
                <Checkbox
                  checked={enabledFilters.loudness !== false}
                  onCheckedChange={(checked) => toggleFilter('loudness', checked as boolean)}
                />
              </div>
              <Slider
                value={loudnessRange}
                onValueChange={([min, max]) => {
                  updatePreference('min_loudness', min)
                  updatePreference('max_loudness', max)
                }}
                max={0}
                min={-60}
                step={2}
                className="w-full"
                disabled={enabledFilters.loudness === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Quiet ({loudnessRange[0]})</span>
                <span>Loud ({loudnessRange[1]})</span>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Genre Matching Weight</Label>
                <Checkbox
                  checked={enabledFilters.genre !== false}
                  onCheckedChange={(checked) => toggleFilter('genre', checked as boolean)}
                />
              </div>
              <Slider
                value={[preferences.genre_weight || 0.7]}
                onValueChange={([value]) => updatePreference('genre_weight', value)}
                max={1}
                min={0}
                step={0.1}
                className="w-full"
                disabled={enabledFilters.genre === false}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Diverse ({(preferences.genre_weight || 0.7).toFixed(1)})</span>
                <span>Same Genre</span>
              </div>
            </div>
          </>
        )}

        <div className="space-y-3">
          <Label className="text-sm font-medium">Recommendation Algorithm</Label>
          <Select value={preferences.algorithm || 'lastfm'} onValueChange={(value) => updatePreference('algorithm', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Select algorithm" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="lastfm">
                <div className="flex flex-col">
                  <span>Last.fm (Default)</span>
                  <span className="text-xs text-muted-foreground">Collaborative filtering based on user listening patterns</span>
                </div>
              </SelectItem>
              <SelectItem value="custom">
                <div className="flex flex-col">
                  <span>Custom (Content-Based)</span>
                  <span className="text-xs text-muted-foreground">Cosine similarity on librosa audio features (energy, valence, tempo, timbre)</span>
                </div>
              </SelectItem>
              <SelectItem value="audio">
                <div className="flex flex-col">
                  <span>Audio MFCC Similarity</span>
                  <span className="text-xs text-muted-foreground">Timbre matching using MFCC coefficients extracted from 30s previews</span>
                </div>
              </SelectItem>
              <SelectItem value="structural">
                <div className="flex flex-col">
                  <span>Structural Analysis</span>
                  <span className="text-xs text-muted-foreground">Pattern matching using self-similarity matrices and section clustering</span>
                </div>
              </SelectItem>
              <SelectItem value="clap">
                <div className="flex flex-col">
                  <span>CLAP Deep Embeddings ✨</span>
                  <span className="text-xs text-muted-foreground">Deep learning audio embeddings via laion/larger_clap_music (512-dim vectors)</span>
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
          <div className="text-xs text-muted-foreground">
            {preferences.algorithm === 'custom'
              ? 'Content-based filtering using librosa audio features (energy, valence, tempo, MFCCs, chroma). Requires preview URLs.'
              : preferences.algorithm === 'audio'
              ? 'MFCC timbre similarity — finds songs that sound alike based on timbral features extracted from audio previews.'
              : preferences.algorithm === 'structural'
              ? 'Structural analysis using self-similarity matrices and section clustering to match songs with similar musical form.'
              : preferences.algorithm === 'clap'
              ? 'Deep learning embeddings via CLAP (laion/larger_clap_music). Captures timbre, mood, and musical style in a 512-dim vector. First run downloads ~335 MB model.'
              : "Using Last.fm's collaborative filtering based on millions of user listening habits"
            }
          </div>
        </div>

        <div className="space-y-3">
          <Label className="text-sm font-medium">Market</Label>
          <Select value={preferences.market || 'US'} onValueChange={(value) => updatePreference('market', value)}>
            <SelectTrigger>
              <SelectValue placeholder="Select market" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="US">United States</SelectItem>
              <SelectItem value="GB">United Kingdom</SelectItem>
              <SelectItem value="CA">Canada</SelectItem>
              <SelectItem value="AU">Australia</SelectItem>
              <SelectItem value="DE">Germany</SelectItem>
              <SelectItem value="FR">France</SelectItem>
              <SelectItem value="ES">Spain</SelectItem>
              <SelectItem value="IT">Italy</SelectItem>
              <SelectItem value="BR">Brazil</SelectItem>
              <SelectItem value="JP">Japan</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  )
}