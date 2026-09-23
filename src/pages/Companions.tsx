import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Heart, Loader2, Music2, Plus, ShieldAlert, UserRoundCheck, UsersRound, X } from 'lucide-react'
import { apiClient, type CompanionCandidate, type CompanionConcert, type CompanionMatch, type CompanionProfile } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

const blankProfile = { display_name: '', bio: '', city: '', public_interests: [], visible: true, music_affinity_consent: true, adult_confirmed: false }

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Probá de nuevo en unos minutos.'
}

export default function Companions() {
  const { toast } = useToast()
  const [profile, setProfile] = useState<Omit<CompanionProfile, 'user_id'>>(blankProfile)
  const [profileReady, setProfileReady] = useState(false)
  const [interestsText, setInterestsText] = useState('')
  const [concerts, setConcerts] = useState<CompanionConcert[]>([])
  const [concertId, setConcertId] = useState('')
  const [candidates, setCandidates] = useState<CompanionCandidate[]>([])
  const [matches, setMatches] = useState<CompanionMatch[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newConcert, setNewConcert] = useState({ artist: '', venue: '', city: '', starts_at: '' })

  const load = async () => {
    setLoading(true)
    const [profileResult, concertsResult, matchesResult] = await Promise.allSettled([
      apiClient.getCompanionProfile(), apiClient.getCompanionConcerts(), apiClient.getCompanionMatches(),
    ])
    if (profileResult.status === 'fulfilled') {
      const { user_id: _, ...saved } = profileResult.value
      setProfile(saved)
      setInterestsText(saved.public_interests.join(', '))
      setProfileReady(true)
    }
    if (concertsResult.status === 'fulfilled') {
      setConcerts(concertsResult.value)
      const activeConcert = concertsResult.value.find((concert) => concert.attending)
      if (activeConcert) {
        setConcertId(activeConcert.id)
        try {
          const result = await apiClient.getCompanionCandidates(activeConcert.id)
          setCandidates(result.candidates)
        } catch { setCandidates([]) }
      }
    }
    if (matchesResult.status === 'fulfilled') setMatches(matchesResult.value.matches)
    setLoading(false)
  }

  useEffect(() => { void load() }, [])

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const saved = await apiClient.saveCompanionProfile({
        ...profile,
        public_interests: interestsText.split(',').map((value) => value.trim()).filter(Boolean).slice(0, 5),
      })
      const { user_id: _, ...next } = saved
      setProfile(next)
      setProfileReady(true)
      toast({ title: 'Perfil listo', description: 'Tu perfil se muestra sólo en los recitales donde te anotás.' })
    } catch (error) {
      toast({ title: 'No pudimos guardar el perfil', description: errorText(error), variant: 'destructive' })
    } finally { setSaving(false) }
  }

  const createConcert = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const concert = await apiClient.createCompanionConcert({ ...newConcert, starts_at: new Date(newConcert.starts_at).toISOString(), status: 'scheduled' })
      setConcerts((items) => [...items, concert])
      setConcertId(concert.id)
      setNewConcert({ artist: '', venue: '', city: '', starts_at: '' })
      toast({ title: 'Recital agregado', description: 'Ahora anotate para empezar a buscar compañía.' })
    } catch (error) { toast({ title: 'No pudimos agregar el recital', description: errorText(error), variant: 'destructive' }) }
  }

  const joinConcert = async (concert: CompanionConcert) => {
    try {
      await apiClient.setCompanionAttendance(concert.id, concert.attending ? 'withdrawn' : 'active')
      setConcerts((items) => items.map((item) => item.id === concert.id ? { ...item, attending: !concert.attending } : item))
      if (!concert.attending) { setConcertId(concert.id); await discover(concert.id) }
    } catch (error) { toast({ title: 'No pudimos actualizar tu inscripción', description: errorText(error), variant: 'destructive' }) }
  }

  const discover = async (id = concertId) => {
    if (!id) return
    try {
      const result = await apiClient.getCompanionCandidates(id)
      setCandidates(result.candidates)
    } catch (error) { toast({ title: 'No pudimos buscar compañía', description: errorText(error), variant: 'destructive' }) }
  }

  const swipe = async (action: 'pass' | 'interested') => {
    const candidate = candidates[0]
    if (!candidate || !concertId) return
    try {
      const result = await apiClient.swipeCompanion(concertId, candidate.user_id, action)
      setCandidates((items) => items.slice(1))
      if (result.matched) {
        toast({ title: '¡Hicieron match!', description: `A vos y a ${candidate.display_name} les pinta ir al mismo recital.` })
        const resultMatches = await apiClient.getCompanionMatches()
        setMatches(resultMatches.matches)
      }
    } catch (error) { toast({ title: 'No pudimos registrar tu acción', description: errorText(error), variant: 'destructive' }) }
  }

  const candidate = candidates[0]
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-background to-background px-4 py-6 text-foreground sm:px-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex items-center justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.22em] text-rose-300">SoundMatch en vivo</p><h1 className="mt-1 text-3xl font-bold">Busco segunda</h1></div>
          <Button asChild variant="outline"><Link to="/">Volver al inicio</Link></Button>
        </header>

        <Card className="border-rose-400/20 bg-card/80"><CardHeader><CardTitle className="flex gap-2"><UserRoundCheck /> Tu perfil público</CardTitle></CardHeader><CardContent>
          <form onSubmit={saveProfile} className="grid gap-4 md:grid-cols-2">
            <div><Label htmlFor="name">Cómo querés que te llamen</Label><Input id="name" required value={profile.display_name} onChange={(e) => setProfile({ ...profile, display_name: e.target.value })} /></div>
            <div><Label htmlFor="city">Ciudad</Label><Input id="city" required value={profile.city} onChange={(e) => setProfile({ ...profile, city: e.target.value })} placeholder="CABA" /></div>
            <div className="md:col-span-2"><Label htmlFor="bio">Una breve bio</Label><Input id="bio" maxLength={280} value={profile.bio} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} placeholder="Voy por la música y una buena charla." /></div>
            <div className="md:col-span-2"><Label htmlFor="interests">Hasta 5 géneros o artistas públicos, separados por coma</Label><Input id="interests" value={interestsText} onChange={(e) => setInterestsText(e.target.value)} placeholder="indie rock, electrónica, Barbi Recanati" /></div>
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={profile.music_affinity_consent} onChange={(e) => setProfile({ ...profile, music_affinity_consent: e.target.checked })} /> Autorizo usar géneros agregados de mis escuchas para calcular afinidad.</label>
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" required checked={profile.adult_confirmed} onChange={(e) => setProfile({ ...profile, adult_confirmed: e.target.checked })} /> Confirmo que soy mayor de edad.</label>
            <Button className="min-h-11 md:col-span-2" disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar perfil</Button>
          </form>
        </CardContent></Card>

        {profileReady && <section className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <div className="space-y-6"><Card><CardHeader><CardTitle className="flex gap-2"><Music2 /> Recitales</CardTitle></CardHeader><CardContent className="space-y-3">
            {concerts.map((concert) => <div key={concert.id} className="rounded-lg border border-border/60 p-3"><b>{concert.artist}</b><p className="text-sm text-muted-foreground">{concert.venue} · {concert.city} · {new Date(concert.starts_at).toLocaleString()}</p><Button className="mt-3 min-h-11" variant={concert.attending ? 'secondary' : 'default'} onClick={() => void joinConcert(concert)}>{concert.attending ? 'Dejar de buscar' : 'Busco segunda'}</Button></div>)}
            {!loading && concerts.length === 0 && <p className="text-sm text-muted-foreground">Todavía no hay recitales. Cargá el primero.</p>}
            <form onSubmit={createConcert} className="space-y-2 border-t pt-4"><p className="font-medium">Cargar recital</p><Input required value={newConcert.artist} onChange={(e) => setNewConcert({ ...newConcert, artist: e.target.value })} placeholder="Artista" /><Input required value={newConcert.venue} onChange={(e) => setNewConcert({ ...newConcert, venue: e.target.value })} placeholder="Venue" /><Input required value={newConcert.city} onChange={(e) => setNewConcert({ ...newConcert, city: e.target.value })} placeholder="Ciudad" /><Input required type="datetime-local" value={newConcert.starts_at} onChange={(e) => setNewConcert({ ...newConcert, starts_at: e.target.value })} /><Button className="min-h-11" type="submit"><Plus className="mr-2 h-4 w-4" />Agregar</Button></form>
          </CardContent></Card>
          <Card className="overflow-hidden border-rose-400/25 bg-card/90"><CardHeader><CardTitle className="flex items-center justify-between gap-2"><span className="flex gap-2"><UsersRound /> Personas para el recital</span>{concertId && <Button variant="ghost" onClick={() => void discover()}>Actualizar</Button>}</CardTitle></CardHeader><CardContent>
            {!concertId ? <p className="py-12 text-center text-muted-foreground">Elegí un recital al que te anotaste.</p> : candidate ? <article aria-live="polite" className="rounded-2xl bg-gradient-to-br from-rose-500/15 via-card to-indigo-500/10 p-5 shadow-2xl"><Badge>{candidate.affinity_level} · {candidate.affinity_score}% afinidad</Badge><h2 className="mt-4 text-3xl font-bold">{candidate.display_name}</h2><p className="mt-2 text-muted-foreground">{candidate.bio || 'Le pinta ir por la música y compartir el plan.'}</p><p className="mt-2 text-sm text-muted-foreground">{candidate.city}</p><div className="mt-4 flex flex-wrap gap-2">{candidate.public_interests.map((interest) => <Badge key={interest} variant="secondary">{interest}</Badge>)}</div><ul className="mt-4 space-y-1 text-sm">{candidate.affinity_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul><div className="mt-6 grid grid-cols-2 gap-3"><Button className="min-h-11" variant="outline" onClick={() => void swipe('pass')} aria-label={`Pasar a ${candidate.display_name}`}><X className="mr-2" />Pasar</Button><Button className="min-h-11 bg-rose-600 hover:bg-rose-700" onClick={() => void swipe('interested')} aria-label={`Marcar interés por ${candidate.display_name}`}><Heart className="mr-2" />Me interesa</Button></div><p className="mt-3 text-center text-xs text-muted-foreground">Usá Tab y Enter para elegir. No hace falta deslizar la tarjeta.</p></article> : <div className="py-12 text-center"><UsersRound className="mx-auto mb-3 h-9 w-9 text-muted-foreground" /><p className="font-medium">Por ahora no hay más personas para mostrar</p><p className="mt-1 text-sm text-muted-foreground">Volvé más tarde o cargá otro recital.</p></div>}
          </CardContent></Card></div>
        </section>}

        <Card><CardHeader><CardTitle className="flex gap-2"><Heart className="text-rose-400" /> Mis matches</CardTitle></CardHeader><CardContent>{matches.length ? <div className="grid gap-3 sm:grid-cols-2">{matches.map((match) => <div className="rounded-lg border p-4" key={match.id}><b>{match.companion.display_name}</b><p className="text-sm text-muted-foreground">{match.concert.artist} · {match.concert.venue}</p><p className="mt-2 text-xs text-muted-foreground">El contacto se habilitará sólo si ambas personas lo aceptan.</p></div>)}</div> : <p className="text-sm text-muted-foreground">Cuando el interés sea mutuo, tus matches aparecen acá.</p>}</CardContent></Card>
        <p className="flex items-center gap-2 text-xs text-muted-foreground"><ShieldAlert className="h-4 w-4" /> No compartimos email, teléfono, ubicación precisa ni tu historial de escucha.</p>
      </div>
    </main>
  )
}
