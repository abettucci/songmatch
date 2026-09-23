# Compañeros para recitales — especificación MVP

## Alcance

SoundMatch permitirá que una persona mayor de edad cree un perfil público opt-in, se anote a un recital y descubra personas que también buscan compañía para ese mismo evento. La experiencia es sólo para descubrir afinidades: no incluye chat, datos de contacto ni ubicación precisa.

## Decisiones de producto

- Un perfil sólo se muestra si `visible`, `adult_confirmed` y `music_affinity_consent` son verdaderos.
- La ciudad es texto amplio, no se almacenan coordenadas ni direcciones.
- Cada usuario puede tener hasta cinco intereses públicos, combinando géneros y artistas.
- Los recitales se cargan manualmente. `ConcertSource` define la interfaz para incorporar una fuente externa más adelante, sin hacer llamadas externas en este MVP.
- Un usuario se anota con un único intent activo por recital.
- Un “interesado/a” crea un match únicamente cuando la otra persona ya expresó interés para el mismo recital. La restricción única de pares y una inserción transaccional hacen al proceso idempotente.
- El contacto futuro exige consentimiento bilateral y queda fuera de v1.

## Modelo de datos

| Tabla | Propósito | Restricciones relevantes |
| --- | --- | --- |
| `user_profiles` | Perfil público opt-in | único `user_id`; nombre 2–50; bio 280; ciudad 2–80; máximo cinco intereses validado por API |
| `concerts` | Recitales manuales | artista, venue, ciudad, `starts_at`, estado (`scheduled`, `cancelled`, `completed`) |
| `concert_attendance_intents` | “Busco segunda” | único `(user_id, concert_id)`; estado `active`/`withdrawn` |
| `companion_swipes` | Pasar o interés | único `(actor_user_id, target_user_id, concert_id)`; acción `pass`/`interested` |
| `companion_matches` | Interés mutuo | único por pareja sin orden y recital, con `user_low_id < user_high_id` |
| `user_blocks` | Bloqueos unidireccionales | único `(blocker_user_id, blocked_user_id)` |
| `user_reports` | Reportes | reportante, perfil reportado, motivo y nota opcional |

## API

Todos los endpoints requieren JWT y aplican ownership checks.

| Método y ruta | Función |
| --- | --- |
| `GET/PUT /api/v1/companions/profile` | Leer o crear/actualizar el perfil propio |
| `GET /api/v1/companions/concerts` | Listar recitales próximos |
| `POST /api/v1/companions/concerts` | Cargar un recital manual |
| `POST /api/v1/companions/concerts/{id}/attendance` | Activar o retirar “busco segunda” |
| `GET /api/v1/companions/concerts/{id}/candidates` | Obtener tarjetas elegibles ordenadas por afinidad |
| `POST /api/v1/companions/concerts/{id}/swipes` | Pasar o marcar interés; devuelve match si lo creó |
| `GET /api/v1/companions/matches` | Ver matches propios |
| `POST /api/v1/companions/blocks` | Bloquear perfil |
| `POST /api/v1/companions/reports` | Reportar perfil |

## Afinidad musical

El backend calcula un score determinista de 0 a 100 y nunca entrega el historial crudo.

1. Los intereses públicos explícitos pesan 70 puntos: cada coincidencia normalizada aporta una fracción igual de ese tramo.
2. Si ambas personas dieron consentimiento, los géneros agregados desde `ListeningHistory` de los últimos 90 días completan hasta 30 puntos. Cada play se pondera por recencia: `1 / (1 + días_desde_reproducción / 30)`.
3. Se conservan hasta tres explicaciones seguras basadas sólo en términos públicos o géneros agregados, por ejemplo “Coinciden en indie rock”.
4. Nivel: `alto` (70–100), `medio` (40–69), `bajo` (0–39). El endpoint descarta candidatos por debajo de 20.

## Privacidad y seguridad

- Las respuestas públicas exponen sólo id de perfil, nombre, bio, ciudad, intereses, afinidad y recital.
- Nunca incluyen email, tokens, historial de escucha, teléfono, coordenadas ni dirección.
- Bloqueos y reportes se procesan server-side. Ambos sentidos de un bloqueo excluyen candidatos y matches.
- Los swipes tienen un límite por usuario en memoria: 30 por minuto, además del limitador global existente.
- Pydantic limita longitudes, enumera estados/acciones y rechaza relaciones a sí mismo.

## Criterios de aceptación

- Un perfil sin consentimiento o invisible no puede aparecer como candidato.
- Un candidato sólo aparece si ambos tienen intent activo para el mismo recital y no existe swipe previo, bloqueo o descarte.
- Un like mutuo crea exactamente un match, incluso con reintentos concurrentes.
- La interfaz ofrece botones visibles, foco de teclado y etiquetas para lector de pantalla; el swipe visual no es necesario para operar.
- La pantalla funciona desde 375 px y muestra estados de carga, vacío y error.

## Plan de pruebas

- Pytest para score, explicaciones, exclusiones, ownership, validación y match idempotente.
- Vitest + React Testing Library para estado vacío, tarjeta/afinidad, acciones y accesibilidad.
- Playwright con API simulada para perfil, asistencia, interés mutuo y match.
- Lint, build, suite frontend, pytest, E2E y Semgrep cuando esté disponible.
