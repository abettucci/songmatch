import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Check, Info, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

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
  algorithm?: AlgorithmKey
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

type AlgorithmKey = 'lastfm' | 'custom' | 'audio' | 'structural' | 'clap'

interface RecommendationSettingsProps {
  preferences: PreferencesType
  onPreferencesChange: (preferences: PreferencesType) => void
}

type RangeFilterKey = Exclude<keyof NonNullable<PreferencesType['enabled_filters']>, 'genre'>

interface RangeFilter {
  key: RangeFilterKey
  label: string
  tip: string
  low: string
  high: string
  min: number
  max: number
  step: number
}

// Plain-language explanations shown on hover. Keep them short and concrete.
const RANGE_FILTERS: RangeFilter[] = [
  {
    key: 'energy', label: 'Energy Level', low: 'Calm', high: 'Energetic', min: 0, max: 1, step: 0.1,
    tip: 'Qué tan intensa se siente la canción. Bajo: tranquila y suave. Alto: con fuerza, ritmo y volumen.',
  },
  {
    key: 'valence', label: 'Mood (Valence)', low: 'Sad', high: 'Happy', min: 0, max: 1, step: 0.1,
    tip: 'Qué tan positiva suena. Bajo: melancólica o triste. Alto: alegre u optimista.',
  },
  {
    key: 'danceability', label: 'Danceability', low: 'Not Danceable', high: 'Very Danceable', min: 0, max: 1, step: 0.1,
    tip: 'Qué tan fácil es bailarla, según el ritmo y qué tan estable es el pulso.',
  },
  {
    key: 'acousticness', label: 'Acousticness', low: 'Electric', high: 'Acoustic', min: 0, max: 1, step: 0.1,
    tip: 'Cuánto suena a instrumentos acústicos (guitarra, piano, voz natural) y no a electrónica muy producida.',
  },
  {
    key: 'instrumentalness', label: 'Instrumentalness', low: 'Vocal', high: 'Instrumental', min: 0, max: 1, step: 0.1,
    tip: 'Qué tan probable es que no tenga voces. Alto: casi sin letra cantada.',
  },
  {
    key: 'liveness', label: 'Liveness', low: 'Studio', high: 'Live', min: 0, max: 1, step: 0.1,
    tip: 'Si suena grabada en vivo, con público. Alto: se nota el recital o la sala.',
  },
  {
    key: 'speechiness', label: 'Speechiness', low: 'Music', high: 'Speech-like', min: 0, max: 1, step: 0.1,
    tip: 'Cuánta palabra hablada tiene (rap, spoken word, podcast). Bajo: casi todo es música.',
  },
  {
    key: 'tempo', label: 'Tempo (BPM)', low: 'Slow', high: 'Fast', min: 60, max: 200, step: 5,
    tip: 'Velocidad en BPM (pulsos por minuto). Cerca de 60 es muy lenta; cerca de 200, muy rápida.',
  },
  {
    key: 'loudness', label: 'Loudness (dB)', low: 'Quiet', high: 'Loud', min: -60, max: 0, step: 2,
    tip: 'Volumen general en decibeles. Cerca de 0: muy fuerte. Cerca de -60: muy suave.',
  },
]

interface AlgorithmInfo {
  label: string
  // Original one-line description, kept as is.
  short: string
  // Longer text shown on hover in the list.
  detail: string
  // Popup sections.
  sources: string[]
  how: string
  note: string
}

const ALGORITHMS: Record<AlgorithmKey, AlgorithmInfo> = {
  lastfm: {
    label: 'Last.fm (Default)',
    short: 'Collaborative filtering based on user listening patterns',
    detail: 'Busca artistas parecidos según lo que escucha mucha gente en Last.fm, y trae sus temas más populares.',
    sources: ['Last.fm: artistas similares y sus temas top', 'Spotify: búsqueda y datos de cada canción'],
    how: 'Toma tus canciones semilla y pide a Last.fm los artistas más parecidos a cada una. De cada uno trae sus 5 temas top, los busca en Spotify y los ordena por puntaje de coincidencia. Descarta artistas que ya están en tu semilla.',
    note: 'Es filtrado colaborativo: se apoya en patrones de escucha de muchos usuarios, no en el audio.',
  },
  custom: {
    label: 'Custom (Content-Based)',
    short: 'Cosine similarity on librosa audio features (energy, valence, tempo, timbre)',
    detail: 'Compara el sonido real de las canciones (energía, ánimo, tempo y timbre) usando el preview de 30 segundos.',
    sources: ['Spotify: artistas relacionados, álbumes y tracks, con preview de 30 s', 'librosa para analizar el audio; Cyanite y Deezer cuando están disponibles'],
    how: 'Analiza el preview de tus semillas con librosa y saca un vector promedio (energía, valence, tempo, MFCC y chroma). Después mide la similitud coseno de cada candidato contra ese vector y se queda con los más cercanos.',
    note: 'Necesita previews de 30 s en las semillas. Si no hay ninguno, no devuelve resultados.',
  },
  audio: {
    label: 'Audio MFCC Similarity',
    short: 'Timbre matching using MFCC coefficients extracted from 30s previews',
    detail: 'Busca canciones que suenen parecido en timbre, midiendo la "huella" del sonido de cada preview.',
    sources: ['Spotify: previews de 30 s y candidatos', 'librosa para extraer los MFCC'],
    how: 'Calcula los coeficientes MFCC del preview de cada semilla y de cada candidato. Los MFCC describen el timbre: cómo suenan los instrumentos y la voz. Compara con similitud coseno y devuelve los más cercanos.',
    note: 'Si las semillas no tienen preview, cae a Last.fm.',
  },
  structural: {
    label: 'Structural Analysis',
    short: 'Pattern matching using self-similarity matrices and section clustering',
    detail: 'Compara la forma de la canción: cómo se repiten y cambian sus secciones (estrofa, estribillo, puente).',
    sources: ['Spotify: previews de 30 s y candidatos', 'librosa para el análisis de estructura'],
    how: 'Construye una matriz de autosimilitud del preview, detecta los cambios de sección (novelty de Foote) y agrupa los segmentos con clustering Ward, siguiendo el pipeline de Martínez (2023). Con esa estructura compara los candidatos.',
    note: 'Tarda más (entre 10 y 30 s). Si no hay análisis de estructura, cae a MFCC.',
  },
  clap: {
    label: 'CLAP Deep Embeddings ✨',
    short: 'Deep learning audio embeddings via laion/larger_clap_music (512-dim vectors)',
    detail: 'Usa un modelo de deep learning que resume el clima musical de cada canción en un vector de 512 números.',
    sources: ['Spotify: previews de 30 s y candidatos', 'Modelo CLAP laion/larger_clap_music (unos 335 MB la primera vez)'],
    how: 'El modelo CLAP convierte cada preview en un vector de 512 dimensiones que resume timbre, ánimo y estilo. Compara los vectores de tus semillas con los de cada candidato y devuelve los más parecidos.',
    note: 'Si las semillas no tienen preview, cae a MFCC.',
  },
}

const ALGORITHM_ORDER: AlgorithmKey[] = ['lastfm', 'custom', 'audio', 'structural', 'clap']

function formatValue(value: number, step: number): string {
  return step < 1 ? value.toFixed(1) : String(value)
}

function RangeFilterRow({
  filter,
  range,
  enabled,
  onToggle,
  onChange,
}: {
  filter: RangeFilter
  range: [number, number]
  enabled: boolean
  onToggle: (enabled: boolean) => void
  onChange: (min: number, max: number) => void
}) {
  const [min, max] = range
  return (
    <div className={cn('space-y-3 rounded-xl border border-border/50 bg-card/60 p-4 transition-opacity', !enabled && 'opacity-60')}>
      <div className="flex items-center justify-between gap-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <button type="button" className="flex cursor-help items-center gap-1.5 text-left text-sm font-medium">
              {filter.label}
              <Info className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs text-sm leading-snug">{filter.tip}</TooltipContent>
        </Tooltip>
        <div className="flex items-center gap-2.5">
          <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium tabular-nums text-primary">
            {formatValue(min, filter.step)} – {formatValue(max, filter.step)}
          </span>
          <Checkbox
            checked={enabled}
            onCheckedChange={(checked) => onToggle(checked === true)}
            aria-label={`Usar filtro ${filter.label}`}
          />
        </div>
      </div>
      <Slider
        value={[min, max]}
        onValueChange={([nextMin, nextMax]) => onChange(nextMin, nextMax)}
        min={filter.min}
        max={filter.max}
        step={filter.step}
        disabled={!enabled}
        aria-label={filter.label}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{filter.low}</span>
        <span>{filter.high}</span>
      </div>
    </div>
  )
}

export function RecommendationSettings({ preferences, onPreferencesChange }: RecommendationSettingsProps) {
  const [infoOpen, setInfoOpen] = useState(false)
  const [infoKey, setInfoKey] = useState<AlgorithmKey>('lastfm')

  const updatePreference = <K extends keyof PreferencesType>(key: K, value: PreferencesType[K]) => {
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
  const currentAlgorithm: AlgorithmKey = preferences.algorithm ?? 'lastfm'
  const infoItem = ALGORITHMS[infoKey]

  const openInfo = () => {
    setInfoKey(currentAlgorithm)
    setInfoOpen(true)
  }

  return (
    <TooltipProvider delayDuration={150}>
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
            <div className="space-y-3">
              {RANGE_FILTERS.map((filter) => {
                const minKey = `min_${filter.key}` as keyof PreferencesType
                const maxKey = `max_${filter.key}` as keyof PreferencesType
                const range: [number, number] = [
                  (preferences[minKey] as number | undefined) ?? filter.min,
                  (preferences[maxKey] as number | undefined) ?? filter.max,
                ]
                return (
                  <RangeFilterRow
                    key={filter.key}
                    filter={filter}
                    range={range}
                    enabled={enabledFilters[filter.key] !== false}
                    onToggle={(enabled) => toggleFilter(filter.key, enabled)}
                    onChange={(min, max) => {
                      onPreferencesChange({ ...preferences, [minKey]: min, [maxKey]: max })
                    }}
                  />
                )
              })}

              <div className={cn('space-y-3 rounded-xl border border-border/50 bg-card/60 p-4', enabledFilters.genre === false && 'opacity-60')}>
                <div className="flex items-center justify-between gap-3">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" className="flex cursor-help items-center gap-1.5 text-left text-sm font-medium">
                        Genre Matching Weight
                        <Info className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-sm leading-snug">
                      Cuánto priorizar el mismo género al recomendar. Hoy este ajuste todavía no cambia el resultado: el backend no lo usa.
                    </TooltipContent>
                  </Tooltip>
                  <div className="flex items-center gap-2.5">
                    <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium tabular-nums text-primary">
                      {(preferences.genre_weight ?? 0.7).toFixed(1)}
                    </span>
                    <Checkbox
                      checked={enabledFilters.genre !== false}
                      onCheckedChange={(checked) => toggleFilter('genre', checked === true)}
                      aria-label="Usar peso de género"
                    />
                  </div>
                </div>
                <Slider
                  value={[preferences.genre_weight ?? 0.7]}
                  onValueChange={([value]) => updatePreference('genre_weight', value)}
                  min={0}
                  max={1}
                  step={0.1}
                  disabled={enabledFilters.genre === false}
                  aria-label="Genre Matching Weight"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Diverse</span>
                  <span>Same Genre</span>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <Label className="text-sm font-medium">Recommendation Algorithm</Label>
              <Button type="button" variant="ghost" size="sm" className="h-7 gap-1.5 px-2 text-xs" onClick={openInfo}>
                <Info className="h-3.5 w-3.5" />
                ¿Cómo funciona?
              </Button>
            </div>
            <div role="radiogroup" aria-label="Recommendation Algorithm" className="space-y-2">
              {ALGORITHM_ORDER.map((key) => {
                const info = ALGORITHMS[key]
                const selected = key === currentAlgorithm
                return (
                  <Tooltip key={key}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        onClick={() => updatePreference('algorithm', key)}
                        className={cn(
                          'flex w-full items-start justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors',
                          selected ? 'border-primary bg-primary/10' : 'border-border/60 bg-background hover:bg-muted/60',
                        )}
                      >
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">{info.label}</span>
                          <span className="block text-xs text-muted-foreground">{info.short}</span>
                        </span>
                        {selected && <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-sm leading-snug">{info.detail}</TooltipContent>
                  </Tooltip>
                )
              })}
            </div>
            <div className="text-xs text-muted-foreground">
              {currentAlgorithm === 'custom'
                ? 'Content-based filtering using librosa audio features (energy, valence, tempo, MFCCs, chroma). Requires preview URLs.'
                : currentAlgorithm === 'audio'
                ? 'MFCC timbre similarity — finds songs that sound alike based on timbral features extracted from audio previews.'
                : currentAlgorithm === 'structural'
                ? 'Structural analysis using self-similarity matrices and section clustering to match songs with similar musical form.'
                : currentAlgorithm === 'clap'
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

        <Dialog open={infoOpen} onOpenChange={setInfoOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{infoItem.label}</DialogTitle>
              <DialogDescription>{infoItem.detail}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-wrap gap-1.5">
              {ALGORITHM_ORDER.map((key) => (
                <Button
                  key={key}
                  type="button"
                  size="sm"
                  variant={key === infoKey ? 'default' : 'outline'}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setInfoKey(key)}
                >
                  {ALGORITHMS[key].label}
                </Button>
              ))}
            </div>
            <div className="space-y-4 text-sm">
              <section className="space-y-1.5">
                <h4 className="font-semibold">Fuentes de datos</h4>
                <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                  {infoItem.sources.map((source) => <li key={source}>{source}</li>)}
                </ul>
              </section>
              <section className="space-y-1.5">
                <h4 className="font-semibold">Cómo recomienda</h4>
                <p className="text-muted-foreground">{infoItem.how}</p>
              </section>
              <p className="rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">{infoItem.note}</p>
              {infoKey === currentAlgorithm && (
                <p className="text-xs font-medium text-primary">Este es el algoritmo que tenés seleccionado.</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </Card>
    </TooltipProvider>
  )
}
