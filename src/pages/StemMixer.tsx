import { FormEvent, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft, Drum, Guitar, Loader2, Music2, Pause, Piano, Play,
  RotateCcw, SlidersHorizontal, Upload, Volume2,
} from 'lucide-react'
import { apiClient, type StemJob, type StemName } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

const STEMS: { id: StemName; label: string; note: string; icon: typeof Music2 }[] = [
  { id: 'vocals', label: 'Voz', note: 'Vocal principal y coros', icon: Music2 },
  { id: 'drums', label: 'Batería', note: 'Percusión y ritmo', icon: Drum },
  { id: 'bass', label: 'Bajo', note: 'Línea de bajo', icon: Volume2 },
  { id: 'other', label: 'Otros', note: 'Acompañamiento y mezcla', icon: SlidersHorizontal },
  { id: 'guitar', label: 'Guitarra', note: 'Guitarras aisladas', icon: Guitar },
  { id: 'piano', label: 'Piano', note: 'Pianos y teclas', icon: Piano },
]
const MAX_FILE_BYTES = 100 * 1024 * 1024
const MAX_FILE_SECONDS = 10 * 60
const ARTIFACTS_HOST = import.meta.env.VITE_STEM_ARTIFACTS_HOST as string | undefined

type Channel = {
  audio: HTMLAudioElement
  source: MediaElementAudioSourceNode
  gain: GainNode
}

function trustedArtifactUrl(rawUrl: string): string {
  const parsed = new URL(rawUrl)
  if (!ARTIFACTS_HOST || parsed.protocol !== 'https:' || parsed.hostname !== ARTIFACTS_HOST) {
    throw new Error('El almacenamiento de audio no está configurado para este sitio.')
  }
  return parsed.toString()
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${minutes}:${remainder}`
}

function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') return error.message
  return 'No pudimos procesar el audio. Probá con otro enlace o archivo.'
}

function StemPlayer({ job }: { job: StemJob }) {
  const contextRef = useRef<AudioContext | null>(null)
  const shifterRef = useRef<AudioWorkletNode | null>(null)
  const channelsRef = useRef<Map<StemName, Channel>>(new Map())
  const [ready, setReady] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volumes, setVolumes] = useState<Record<StemName, number>>({ vocals: 100, drums: 100, bass: 100, other: 100, guitar: 100, piano: 100 })
  const [semitones, setSemitones] = useState(0)
  const [audioError, setAudioError] = useState('')

  useEffect(() => {
    let active = true
    let syncTimer = 0
    const channels = new Map<StemName, Channel>()
    const context = new AudioContext()
    contextRef.current = context

    const initialize = async () => {
      try {
        await context.audioWorklet.addModule('/soundtouch-processor.js')
        if (!active) return
        const limiter = context.createDynamicsCompressor()
        limiter.threshold.value = -2
        limiter.knee.value = 0
        limiter.ratio.value = 16
        limiter.attack.value = 0.003
        limiter.release.value = 0.12
        limiter.connect(context.destination)
        const pitchShifter = new AudioWorkletNode(context, 'soundtouch-processor', {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          outputChannelCount: [2],
        })
        const pitchControl = pitchShifter.parameters.get('pitchSemitones')
        if (!pitchControl) throw new Error('El procesador de tono no está disponible.')
        pitchControl.value = semitones
        pitchShifter.connect(limiter)

        for (const stem of STEMS) {
          const signedUrl = job.stems?.[stem.id]
          if (!signedUrl) throw new Error(`Falta el archivo del stem ${stem.label}.`)
          const audio = new Audio()
          audio.crossOrigin = 'anonymous'
          audio.preload = 'auto'
          audio.src = trustedArtifactUrl(signedUrl)
          audio.addEventListener('loadedmetadata', () => {
            if (stem.id === 'vocals' && Number.isFinite(audio.duration)) setDuration(audio.duration)
          })
          audio.addEventListener('ended', () => {
            channels.forEach((channel) => { channel.audio.pause(); channel.audio.currentTime = 0 })
            setPlaying(false)
            setCurrentTime(0)
          })

          const source = context.createMediaElementSource(audio)
          const gain = context.createGain()
          gain.gain.value = volumes[stem.id] / 100
          source.connect(gain)
          gain.connect(pitchShifter)
          channels.set(stem.id, { audio, source, gain })
        }

        if (!active) return
        channelsRef.current = channels
        shifterRef.current = pitchShifter
        setReady(true)
        syncTimer = window.setInterval(() => {
          const masterTime = channels.get('vocals')?.audio.currentTime ?? 0
          channels.forEach((channel) => {
            if (Math.abs(channel.audio.currentTime - masterTime) > 0.12) channel.audio.currentTime = masterTime
          })
          setCurrentTime(masterTime)
        }, 300)
      } catch (error) {
        if (active) setAudioError(errorMessage(error))
      }
    }

    void initialize()
    return () => {
      active = false
      window.clearInterval(syncTimer)
      channels.forEach((channel) => {
        channel.audio.pause()
        channel.audio.removeAttribute('src')
        channel.audio.load()
        channel.source.disconnect()
        channel.gain.disconnect()
      })
      channels.clear()
      channelsRef.current.clear()
      shifterRef.current?.disconnect()
      shifterRef.current = null
      if (context.state !== 'closed') void context.close()
      contextRef.current = null
    }
  }, [job.id, job.stems])

  const togglePlayback = async () => {
    const channels = channelsRef.current
    const context = contextRef.current
    if (!ready || !context || channels.size !== STEMS.length) return
    if (playing) {
      channels.forEach((channel) => channel.audio.pause())
      setPlaying(false)
      return
    }
    try {
      await context.resume()
      await Promise.all([...channels.values()].map((channel) => channel.audio.play()))
      setPlaying(true)
    } catch {
      setAudioError('El navegador bloqueó la reproducción. Volvé a tocar reproducir.')
    }
  }

  const seek = (value: number[]) => {
    const nextTime = value[0] ?? 0
    channelsRef.current.forEach((channel) => { channel.audio.currentTime = nextTime })
    setCurrentTime(nextTime)
  }

  const changeVolume = (stem: StemName, value: number[]) => {
    const volume = value[0] ?? 100
    setVolumes((current) => ({ ...current, [stem]: volume }))
    const channel = channelsRef.current.get(stem)
    if (channel) channel.gain.gain.setTargetAtTime(volume / 100, contextRef.current?.currentTime ?? 0, 0.02)
  }

  const changeSemitones = (value: number[]) => {
    const nextSemitones = value[0] ?? 0
    setSemitones(nextSemitones)
    shifterRef.current?.parameters.get('pitchSemitones')?.setTargetAtTime(nextSemitones, contextRef.current?.currentTime ?? 0, 0.04)
  }

  return (
    <section className="space-y-6" aria-label="Mixer de stems">
      <Card className="overflow-hidden border-white/10 bg-slate-950 text-white shadow-2xl shadow-black/30">
        <CardContent className="p-5 sm:p-7">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
            <Button
              aria-label={playing ? 'Pausar' : 'Reproducir'}
              disabled={!ready}
              onClick={() => void togglePlayback()}
              className="h-16 w-16 shrink-0 rounded-full bg-lime-300 text-slate-950 hover:bg-lime-200"
            >
              {!ready ? <Loader2 className="h-6 w-6 animate-spin" /> : playing ? <Pause className="h-6 w-6 fill-current" /> : <Play className="ml-1 h-6 w-6 fill-current" />}
            </Button>
            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex items-center justify-between gap-4 text-xs tabular-nums text-slate-400">
                <span>{ready ? 'MEZCLA EN VIVO' : 'PREPARANDO CANALES'}</span>
                <span>{formatTime(currentTime)} <span className="text-slate-600">/</span> {formatTime(duration)}</span>
              </div>
              <Slider
                aria-label="Posición de reproducción"
                min={0}
                max={Math.max(duration, 0.1)}
                step={0.1}
                value={[Math.min(currentTime, duration || 0)]}
                onValueChange={seek}
                disabled={!ready || !duration}
                className="py-2"
              />
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500">
                <span>Seis stems sincronizados</span>
                <span>Los cambios se escuchan al instante</span>
              </div>
            </div>
          </div>
          {audioError && <p role="alert" className="mt-4 text-sm text-rose-300">{audioError}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {STEMS.map(({ id, label, note, icon: Icon }, index) => (
          <Card key={id} className="group overflow-hidden border-white/10 bg-slate-900/80 text-white transition-colors hover:border-lime-300/40">
            <CardContent className="p-5">
              <div className="mb-6 flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className={`grid h-10 w-10 place-items-center rounded-xl ${index % 2 === 0 ? 'bg-lime-300/10 text-lime-300' : 'bg-cyan-300/10 text-cyan-300'}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div><h3 className="font-semibold">{label}</h3><p className="mt-0.5 text-xs text-slate-500">{note}</p></div>
                </div>
                <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] tabular-nums text-slate-400">{volumes[id]}%</span>
              </div>
              <div className="flex items-center gap-3">
                <Volume2 className="h-4 w-4 shrink-0 text-slate-500" />
                <Slider
                  aria-label={`Volumen de ${label}`}
                  min={0}
                  max={100}
                  step={1}
                  value={[volumes[id]]}
                  onValueChange={(value) => changeVolume(id, value)}
                  disabled={!ready}
                />
              </div>
              <div className="mt-3 flex justify-between text-[10px] uppercase tracking-[0.16em] text-slate-600"><span>Silencio</span><span>Máximo</span></div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-lime-300/20 bg-lime-300/[0.04] text-white">
        <CardContent className="grid gap-5 p-5 sm:grid-cols-[1fr_auto] sm:items-center sm:p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-lime-300">Tonalidad</p>
            <h3 className="mt-1 text-lg font-semibold">Transponer sin cambiar el tempo</h3>
            <p className="mt-1 text-sm text-slate-400">Mueve los seis stems juntos. Por ejemplo, +1 semitono lleva Eb a E.</p>
          </div>
          <div className="flex items-center gap-4 sm:w-72">
            <span className="w-8 text-right text-sm tabular-nums text-slate-500">−12</span>
            <Slider
              aria-label="Transposición en semitonos"
              min={-12}
              max={12}
              step={1}
              value={[semitones]}
              onValueChange={changeSemitones}
              disabled={!ready}
            />
            <span className="w-8 text-sm tabular-nums text-slate-500">+12</span>
            <span className="w-16 text-right font-mono text-lg font-semibold text-lime-300">{semitones > 0 ? `+${semitones}` : semitones} st</span>
            <Button variant="ghost" size="icon" aria-label="Restablecer tonalidad" onClick={() => changeSemitones([0])} disabled={!ready} className="text-slate-400 hover:text-white">
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

export default function StemMixer() {
  const [sourceMode, setSourceMode] = useState<'spotify' | 'upload'>('spotify')
  const [spotifyUrl, setSpotifyUrl] = useState('')
  const [job, setJob] = useState<StemJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [jobError, setJobError] = useState('')
  const [fallbackAvailable, setFallbackAvailable] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!job || !['queued', 'processing'].includes(job.status)) return
    let active = true
    let timer = 0
    const poll = async () => {
      try {
        const next = await apiClient.getStemJob(job.id)
        if (!active) return
        setJob(next)
        if (next.status === 'failed') {
          setJobError(next.error_code === 'worker_timeout'
            ? 'La separación tardó demasiado. Intentá de nuevo con un audio más corto.'
            : 'No pudimos separar ese audio. Podés probar con un archivo de audio.')
          if (job.source_type === 'spotify') setFallbackAvailable(true)
        } else if (next.status !== 'completed') {
          timer = window.setTimeout(() => { void poll() }, 1800)
        }
      } catch (error) {
        if (!active) return
        // A transient status request failure should not strand an active job.
        setJobError(errorMessage(error))
        timer = window.setTimeout(() => { void poll() }, 2500)
      }
    }
    timer = window.setTimeout(() => { void poll() }, 1200)
    return () => { active = false; window.clearTimeout(timer) }
  }, [job?.id, job?.status])

  const startSpotifyJob = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setJobError('')
    setFallbackAvailable(false)
    setJob(null)
    try {
      const created = await apiClient.createStemJob({ source_type: 'spotify', spotify_url: spotifyUrl.trim() })
      setJob(created)
      if (created.status === 'failed') {
        setJobError('No se pudo iniciar la separación. Podés probar con un archivo de audio.')
        setFallbackAvailable(true)
      }
    } catch (error) {
      setJobError(errorMessage(error))
      setFallbackAvailable(true)
    } finally { setBusy(false) }
  }

  const startUploadJob = async (event: FormEvent) => {
    event.preventDefault()
    const file = fileInputRef.current?.files?.[0]
    if (!file) { setJobError('Elegí un archivo de audio para continuar.'); return }
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!['mp3', 'wav', 'm4a'].includes(extension ?? '')) { setJobError('Usá un archivo MP3, WAV o M4A.'); return }
    if (file.size <= 0 || file.size > MAX_FILE_BYTES) { setJobError('El archivo debe pesar menos de 100 MB.'); return }
    if (!ARTIFACTS_HOST) { setJobError('La carga temporal de audio no está configurada.'); return }

    setBusy(true)
    setJobError('')
    setJob(null)
    try {
      const grant = await apiClient.createStemUpload(file)
      const uploadUrl = trustedArtifactUrl(grant.upload_url)
      const formData = new FormData()
      Object.entries(grant.fields).forEach(([name, value]) => formData.append(name, value))
      formData.append('file', file)
      const response = await fetch(uploadUrl, { method: 'POST', body: formData })
      if (!response.ok) throw new Error('No se pudo cargar el archivo. Intentá de nuevo.')
      const created = await apiClient.createStemJob({ source_type: 'upload', source_key: grant.source_key })
      setJob(created)
      if (created.status === 'failed') setJobError('No pudimos iniciar la separación. Intentá de nuevo.')
    } catch (error) {
      setJobError(errorMessage(error))
    } finally { setBusy(false) }
  }

  const processing = job?.status === 'queued' || job?.status === 'processing'
  const title = job?.status === 'completed' ? 'Tu mezcla está lista' : processing ? 'Separando la canción' : 'Escuchá cada capa por separado'

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_rgba(163,230,53,0.09),_transparent_38%),linear-gradient(180deg,#020617_0%,hsl(var(--background))_55%)] px-4 py-6 text-foreground sm:px-6 sm:py-9">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="flex items-center justify-between gap-4">
          <div>
            <Link to="/" className="mb-5 inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"><ArrowLeft className="h-4 w-4" /> Volver a SoundMatch</Link>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-lime-300">AI STEM MIXER <span className="text-slate-600">/</span> SOUND MATCH</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">Separá voz, batería, bajo, otros, guitarra y piano. Ajustá el volumen de cada canal y transponé manteniendo el tempo.</p>
          </div>
          <div className="hidden h-14 w-14 shrink-0 place-items-center rounded-2xl border border-lime-300/20 bg-lime-300/[0.06] text-lime-300 sm:grid"><SlidersHorizontal className="h-6 w-6" /></div>
        </header>

        {job?.status === 'completed' && job.stems ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-xs text-slate-400">
              <span>Archivos temporales · se borran en 24 horas</span>
              <Button variant="ghost" size="sm" onClick={() => { setJob(null); setJobError(''); setFallbackAvailable(false) }} className="text-slate-300 hover:text-white">Procesar otra canción</Button>
            </div>
            <StemPlayer key={job.id} job={job} />
          </>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
            <Card className="border-white/10 bg-slate-950/70 text-white">
              <CardContent className="p-5 sm:p-7">
                <div className="mb-6 flex gap-2 rounded-xl bg-slate-900 p-1">
                  <button onClick={() => { setSourceMode('spotify'); setJobError('') }} className={`flex-1 rounded-lg px-3 py-2.5 text-sm transition-colors ${sourceMode === 'spotify' ? 'bg-lime-300 text-slate-950' : 'text-slate-400 hover:text-white'}`}>Spotify primero</button>
                  <button onClick={() => { setSourceMode('upload'); setJobError('') }} className={`flex-1 rounded-lg px-3 py-2.5 text-sm transition-colors ${sourceMode === 'upload' ? 'bg-lime-300 text-slate-950' : 'text-slate-400 hover:text-white'}`}>Subir archivo</button>
                </div>

                {sourceMode === 'spotify' ? (
                  <form onSubmit={(event) => void startSpotifyJob(event)} className="space-y-4">
                    <div>
                      <Label htmlFor="spotify-track" className="text-sm text-slate-200">Enlace de la canción en Spotify</Label>
                      <Input id="spotify-track" type="url" required value={spotifyUrl} onChange={(event) => setSpotifyUrl(event.target.value)} placeholder="https://open.spotify.com/track/..." className="mt-2 h-12 border-white/10 bg-slate-900 text-white placeholder:text-slate-600" />
                    </div>
                    <Button disabled={busy || processing} className="h-12 w-full bg-lime-300 font-semibold text-slate-950 hover:bg-lime-200">
                      {busy ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Iniciando…</> : <><Play className="mr-2 h-4 w-4" /> Separar canción</>}
                    </Button>
                    <p className="text-xs leading-5 text-slate-500">El enlace se resuelve con el flujo existente. Si no se encuentra el audio, podés cargar un archivo propio.</p>
                  </form>
                ) : (
                  <form onSubmit={(event) => void startUploadJob(event)} className="space-y-4">
                    <div>
                      <Label htmlFor="audio-file" className="text-sm text-slate-200">Archivo de audio</Label>
                      <div className="mt-2 rounded-xl border border-dashed border-slate-700 bg-slate-900/70 p-5">
                        <Input ref={fileInputRef} id="audio-file" type="file" required accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4" className="border-0 bg-transparent p-0 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-lime-300 file:px-3 file:py-2 file:font-medium file:text-slate-950" />
                        <p className="mt-4 text-xs text-slate-500">MP3, WAV o M4A · hasta 100 MB · hasta 10 minutos</p>
                      </div>
                    </div>
                    <Button disabled={busy || processing} className="h-12 w-full bg-lime-300 font-semibold text-slate-950 hover:bg-lime-200">
                      {busy ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Subiendo y preparando…</> : <><Upload className="mr-2 h-4 w-4" /> Cargar y separar</>}
                    </Button>
                  </form>
                )}

                {jobError && <div role="alert" className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/5 p-3 text-sm leading-5 text-rose-200">{jobError}{fallbackAvailable && sourceMode === 'spotify' && <button className="ml-1 font-semibold underline underline-offset-4" onClick={() => setSourceMode('upload')}>Cargar un archivo</button>}</div>}
                {processing && <div className="mt-5 flex items-center gap-3 rounded-lg border border-lime-300/15 bg-lime-300/[0.04] p-3 text-sm text-lime-200"><Loader2 className="h-4 w-4 animate-spin" /><span>{job.status === 'queued' ? 'En cola para procesar…' : 'Separando seis stems con IA…'}</span></div>}
              </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2">
              {STEMS.map(({ id, label, note, icon: Icon }, index) => (
                <div key={id} className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-950/50 p-5">
                  <div className="absolute -right-5 -top-5 h-24 w-24 rounded-full bg-lime-300/[0.04] blur-2xl" />
                  <div className="relative flex items-center gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${index % 2 ? 'bg-cyan-300/10 text-cyan-300' : 'bg-lime-300/10 text-lime-300'}`}><Icon className="h-5 w-5" /></span><div><h2 className="font-semibold text-white">{label}</h2><p className="text-xs text-slate-500">{note}</p></div></div>
                  <div className="mt-5 h-1 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full w-2/3 rounded-full bg-gradient-to-r from-lime-300/60 to-cyan-300/40" /></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.08] pt-4 text-xs text-slate-600">
          <span>Demucs · seis canales · mezcla en tiempo real</span>
          <span>Audio y stems temporales, privados y con expiración de 24 horas</span>
        </footer>
      </div>
    </main>
  )
}
