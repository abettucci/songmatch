import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { vi } from 'vitest'
import Companions from './Companions'

afterEach(cleanup)

const { api } = vi.hoisted(() => ({ api: { getCompanionProfile: vi.fn(), getCompanionConcerts: vi.fn(), getCompanionMatches: vi.fn(), saveCompanionProfile: vi.fn(), createCompanionConcert: vi.fn(), setCompanionAttendance: vi.fn(), getCompanionCandidates: vi.fn(), swipeCompanion: vi.fn() } }))
vi.mock('@/lib/api-client', () => ({ apiClient: api }))
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: vi.fn() }) }))

beforeEach(() => {
  vi.clearAllMocks()
  api.getCompanionProfile.mockResolvedValue({ user_id: 'me', display_name: 'Yo', bio: '', city: 'CABA', public_interests: [], visible: true, music_affinity_consent: true, adult_confirmed: true })
  api.getCompanionConcerts.mockResolvedValue([])
  api.getCompanionMatches.mockResolvedValue({ matches: [] })
})

it('shows the empty recital state', async () => {
  render(<BrowserRouter><Companions /></BrowserRouter>)
  expect(await screen.findByText('Todavía no hay recitales. Cargá el primero.')).toBeInTheDocument()
})

it('shows affinity and supports an accessible interested button', async () => {
  api.getCompanionProfile.mockResolvedValue({ user_id: 'me', display_name: 'Yo', bio: '', city: 'CABA', public_interests: ['indie rock'], visible: true, music_affinity_consent: true, adult_confirmed: true })
  api.getCompanionConcerts.mockResolvedValue([{ id: 'concert-1', artist: 'Bandalos Chinos', venue: 'Movistar Arena', city: 'CABA', starts_at: '2026-12-01T20:00:00Z', status: 'scheduled', attending: true }])
  api.getCompanionCandidates.mockResolvedValue({ concert: {}, candidates: [{ user_id: 'other', display_name: 'Luz', bio: 'Voy sola', city: 'CABA', public_interests: ['indie rock'], affinity_score: 75, affinity_level: 'alto', affinity_reasons: ['Coinciden en indie rock'] }] })
  api.swipeCompanion.mockResolvedValue({ matched: false })
  const user = userEvent.setup()
  render(<BrowserRouter><Companions /></BrowserRouter>)
  expect(await screen.findByText(/75% afinidad/)).toBeInTheDocument()
  expect(screen.getByText('Usá Tab y Enter para elegir. No hace falta deslizar la tarjeta.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Marcar interés por Luz' }))
  expect(api.swipeCompanion).toHaveBeenCalledWith('concert-1', 'other', 'interested')
})
