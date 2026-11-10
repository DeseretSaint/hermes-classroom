/* ── H-196 · the Workshop ───────────────────────────────────────────────────────────────────
 * A local storefront over packs that already exist on this machine. Nothing here is a server, a
 * marketplace or a second home: Discover renders the catalogue this build ships, Library is the
 * installed-pack shelf (the same `library.list` read the route always used), and Provenance is the
 * imported-pack ledger (`pack.list` / `pack.preview`). The one write is "Add to library", which
 * posts a catalogue id to the host seam and lets the existing atomic import path do the work.
 *
 * Honesty rules this surface is built around:
 *   - a card's cover is the pack's own visual artifact, served by `/media/:id`; a pack with no real
 *     visual gets a quiet typographic cover, never a drawn shape standing in for art;
 *   - "Validated" is two named machine checks (hashes match, automated pack checks passed) and the
 *     page prints that sentence beside the word. It is never "safe", "verified" or a human review;
 *   - no rating, learner count, price, XP or streak exists on this surface, and there is no field
 *     that could carry one;
 *   - one primary action per object: Add to library, or Continue when the pack is already held.
 */

const WORKSHOP_TABS = Object.freeze([
  { id: 'discover', label: 'Discover' },
  { id: 'library', label: 'Library' },
  { id: 'provenance', label: 'Provenance' }
])

/** The learner's own shelves. A user category is a bookmark, not a second taxonomy. */
const WORKSHOP_USER_CATEGORIES = Object.freeze(['Learning', 'Teaching', 'Reference', 'Later'])

const WORKSHOP_BADGE = Object.freeze({
  validated: 'Validated',
  community: 'Community',
  validatedNote:
    'Validated on this page means two machine checks: every file matches its manifest hash, and the automated pack checks passed. It is not a human review and not a claim that the teaching is right.',
  communityNote:
    'Community means this pack has not passed both machine checks here. That is not a verdict on the teaching either way.'
})

/** Four quiet fields for the typographic cover; the identity's own tokens, no new colours. */
const WORKSHOP_TONES = Object.freeze(['accent-soft', 'plum-soft', 'lamp-soft', 'paper-raised'])

/** A state heading on the Workshop surfaces: an h2 region, never a competing display plate. */
const workshopStateHeadingStyle = Object.freeze({
  margin: 0,
  fontFamily: CB_SERIF,
  fontSize: CB_TYPE.heading,
  fontWeight: 600,
  lineHeight: 1.2,
  color: 'var(--cb-ink)'
})

const workshopStateBodyStyle = Object.freeze({
  margin: 0,
  fontFamily: CB_SANS,
  fontSize: CB_TYPE.body,
  lineHeight: 1.6,
  color: 'var(--cb-ink)'
})

function workshopTone(packId) {
  const text = String(packId || '')
  let sum = 0
  for (let index = 0; index < text.length; index += 1) sum += text.charCodeAt(index)
  return WORKSHOP_TONES[sum % WORKSHOP_TONES.length]
}

function workshopBadge(item) {
  const validated = Boolean(item && item.validated)
  return {
    word: validated ? WORKSHOP_BADGE.validated : WORKSHOP_BADGE.community,
    note: validated ? WORKSHOP_BADGE.validatedNote : WORKSHOP_BADGE.communityNote,
    tone: validated ? 'field' : 'ink-soft'
  }
}

function workshopMinutes(item) {
  const minutes = Number(item && item.minutes)
  return Number.isFinite(minutes) && minutes > 0 ? `${minutes} min` : null
}

function workshopMetaLine(item) {
  return [item.level_label, item.locale, workshopMinutes(item), `v${item.pack_version}`]
    .filter(Boolean)
    .join(' · ')
}

function workshopFileSize(bytes) {
  const value = Number(bytes) || 0
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${value} B`
}

/* The learner's Workshop bookmarks: profile-scoped device state, never progress. */
const workshopPrefsCache = new Map()
const workshopPrefsListeners = new Set()

function sanitizeWorkshopPrefs(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const favorites = []
  for (const packId of Array.isArray(source.favorites) ? source.favorites : []) {
    if (typeof packId === 'string' && packId && packId.length <= 128 && favorites.indexOf(packId) < 0) {
      favorites.push(packId)
    }
    if (favorites.length >= 200) break
  }
  const categories = {}
  if (source.categories && typeof source.categories === 'object') {
    for (const packId of Object.keys(source.categories)) {
      const value = source.categories[packId]
      if (packId.length <= 128 && WORKSHOP_USER_CATEGORIES.indexOf(value) >= 0) categories[packId] = value
    }
  }
  return { favorites, categories }
}

function readWorkshopPrefs(profile) {
  const key = profile || 'default'
  if (workshopPrefsCache.has(key)) return workshopPrefsCache.get(key)
  let raw = null
  const storage = cbPrefsStorage()
  try {
    raw = storage ? storage.get(`workshop-preferences.${key}`, null) : null
  } catch (error) {
    raw = null
  }
  const value = sanitizeWorkshopPrefs(raw)
  workshopPrefsCache.set(key, value)
  return value
}

function writeWorkshopPrefs(profile, next) {
  const key = profile || 'default'
  const clean = sanitizeWorkshopPrefs(next)
  workshopPrefsCache.set(key, clean)
  const storage = cbPrefsStorage()
  try {
    if (storage) storage.set(`workshop-preferences.${key}`, clean)
  } catch (error) {
    // The cache still changes for this session; the next mount re-reads storage, so a lost write is
    // visible rather than silently assumed saved.
  }
  for (const listener of workshopPrefsListeners) {
    try {
      listener(clean)
    } catch (error) {
      // One broken subscriber must not stop the others.
    }
  }
  return clean
}

function useCbWorkshopPrefs() {
  const profile = cbPrefsProfile()
  const [prefs, setPrefs] = useState(() => readWorkshopPrefs(profile))
  useEffect(() => {
    setPrefs(readWorkshopPrefs(profile))
    const listener = (value) => setPrefs(value)
    workshopPrefsListeners.add(listener)
    return () => workspaceListenersCleanup(listener)
  }, [profile])
  const toggleFavorite = useCallback(
    (packId) => {
      const current = readWorkshopPrefs(profile)
      const has = current.favorites.indexOf(packId) >= 0
      const favorites = has
        ? current.favorites.filter((value) => value !== packId)
        : current.favorites.concat([packId])
      return writeWorkshopPrefs(profile, { ...current, favorites })
    },
    [profile]
  )
  const setCategory = useCallback(
    (packId, category) => {
      const current = readWorkshopPrefs(profile)
      const categories = { ...current.categories }
      if (!category) delete categories[packId]
      else categories[packId] = category
      return writeWorkshopPrefs(profile, { ...current, categories })
    },
    [profile]
  )
  return [prefs, toggleFavorite, setCategory, profile]
}

function workspaceListenersCleanup(listener) {
  workshopPrefsListeners.delete(listener)
}

/** One read of the catalogue. A refusal is a named state, never an empty store. */
function useWorkshopCatalog(enabled) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [ticket, setTicket] = useState(0)
  useEffect(() => {
    if (!enabled) {
      setState({ status: 'idle', data: null, error: null })
      return undefined
    }
    let live = true
    setState((previous) => ({ status: 'loading', data: previous.data, error: null }))
    rest('/workshop/catalog')
      .then((response) => {
        if (!live) return
        if (response && response.ok === true && Array.isArray(response.items)) {
          setState({ status: 'ready', data: response, error: null })
        } else {
          setState({
            status: 'error',
            data: null,
            error: {
              code: (response && response.code) || 'WORKSHOP_UNAVAILABLE',
              message: (response && response.message) || 'The Workshop catalogue could not be read.'
            }
          })
        }
      })
      .catch((error) => {
        if (!live) return
        setState({
          status: 'error',
          data: null,
          error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
        })
      })
    return () => {
      live = false
    }
  }, [enabled, ticket])
  const reload = useCallback(() => setTicket((value) => value + 1), [])
  return { ...state, reload }
}

/**
 * One cover. A real artifact is framed as a printed plate: a paper mount, a thin rule and a lamp
 * spine. A pack with no visual gets type — its category, its title and a rule — with no invented
 * shape, gradient or seal.
 */
function WorkshopCover({ item, layout, hero, caption, revealStyle }) {
  const cover = (item && item.cover) || { kind: 'typographic' }
  const preview = useArtifactPreview(cover.kind === 'artifact' ? cover.artifact_id : null)
  const tone = workshopTone(item && item.pack_id)
  const image = cover.kind === 'artifact' && preview.state === 'ready' ? preview.data_url : null
  const ratio = hero ? '16 / 9' : '3 / 2'
  const alt = (cover.alt && String(cover.alt)) || (item && item.title) || 'Pack cover'
  const failed = cover.kind === 'artifact' && preview.state === 'text'
  return jsxs('figure', {
    'data-cb-workshop-cover': (item && item.pack_id) || 'none',
    'data-cb-workshop-cover-kind': image ? 'artifact' : 'typographic',
    style: {
      margin: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
      minWidth: 0,
      ...(revealStyle || {})
    },
    children: [
      jsxs('div', {
        style: {
          position: 'relative',
          aspectRatio: ratio,
          minHeight: hero ? '12rem' : '5.5rem',
          borderRadius: '2px',
          // Depth is drawn with rules, never with shadow (H-152). The hero plate carries the
          // lamp underline; every other cover keeps the hairline rule.
          border: '1px solid var(--cb-rule)',
          borderBottom: hero ? '2px solid var(--cb-lamp)' : '1px solid var(--cb-rule)',
          background: `var(--cb-${tone})`,
          overflow: 'hidden'
        },
        children: [
          jsx('span', {
            'aria-hidden': 'true',
            style: {
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: '6px',
              background: 'var(--cb-lamp)'
            }
          }),
          image
            ? jsx('img', {
                alt,
                src: image,
                loading: hero ? 'eager' : 'lazy',
                'data-cb-workshop-cover-image': '',
                style: {
                  display: 'block',
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  objectPosition: 'center',
                  background: 'var(--cb-paper)'
                }
              })
            : jsxs('div', {
                'data-cb-workshop-typographic': '',
                style: {
                  boxSizing: 'border-box',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'flex-end',
                  gap: '0.35rem',
                  padding: hero ? '1.1rem 1.25rem 1.15rem 1.5rem' : '0.7rem 0.8rem 0.75rem 1rem'
                },
                children: [
                  jsx('div', {
                    style: {
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      fontWeight: 600,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      color: 'var(--cb-ink-soft)'
                    },
                    children: (item && item.categories && item.categories[0]) || 'Coursebook pack'
                  }),
                  jsx('div', {
                    'aria-hidden': true,
                    style: {
                      width: '2.5rem',
                      borderTop: '2px solid var(--cb-ink)'
                    }
                  }),
                  jsx('div', {
                    style: {
                      fontFamily: CB_SERIF,
                      // Deliberate: a pack title on a cover sits at the heading step, never at
                      // `display`. The identity allows one display plate per route and the route
                      // header's `h1` already owns it, so a cover that took `display` would be a
                      // second plate. The cover is a plate inside the page, not the page title.
                      fontSize: hero ? CB_TYPE.heading : CB_TYPE.lead,
                      fontWeight: 600,
                      lineHeight: 1.15,
                      letterSpacing: '-0.01em',
                      color: 'var(--cb-ink)',
                      overflowWrap: 'anywhere',
                      display: '-webkit-box',
                      WebkitLineClamp: hero ? 3 : 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    },
                    children: (item && item.title) || 'Untitled pack'
                  })
                ]
              })
        ]
      }),
      caption && (image || failed)
        ? jsx('figcaption', {
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              lineHeight: 1.45,
              color: 'var(--cb-ink-soft)'
            },
            children: failed ? `${cover.caption || 'Pack visual'} — the pack’s image could not be read here; the text equivalent stands beside it.` : cover.caption || 'Pack visual'
          })
        : null
    ]
  })
}

function WorkshopBadge({ item, id }) {
  const badge = workshopBadge(item)
  return jsx('span', {
    'data-cb-workshop-badge': badge.word === WORKSHOP_BADGE.validated ? 'validated' : 'community',
    'aria-describedby': id,
    title: badge.note,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.3rem',
      padding: '0.1rem 0.4rem',
      borderRadius: '999px',
      border: `1px solid ${badge.word === WORKSHOP_BADGE.validated ? 'var(--cb-field)' : 'var(--cb-rule)'}`,
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      color: badge.word === WORKSHOP_BADGE.validated ? 'var(--cb-field)' : 'var(--cb-ink-soft)',
      background: 'var(--cb-paper)',
      whiteSpace: 'nowrap'
    },
    children: badge.word
  })
}

/** The sentence a badge is allowed to mean. It is printed once per surface, not hidden in a tooltip. */
function WorkshopTrustNote({ item, id }) {
  const badge = workshopBadge(item)
  return jsx('p', {
    id,
    style: {
      margin: 0,
      maxWidth: CB_MEASURE,
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      lineHeight: 1.5,
      color: 'var(--cb-ink-soft)'
    },
    children: badge.note
  })
}

function WorkshopMeta({ item }) {
  return jsxs('div', {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: '0.35rem 0.55rem',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      color: 'var(--cb-ink-soft)',
      minWidth: 0
    },
    children: [
      item.categories && item.categories[0]
        ? jsx('span', { style: { fontWeight: 600, color: 'var(--cb-ink)' }, children: item.categories[0] })
        : null,
      jsx('span', { children: workshopMetaLine(item) }),
      item.installed
        ? jsx('span', {
            'data-cb-workshop-installed': '',
            style: { color: 'var(--cb-field)', fontWeight: 600 },
            children: 'In your library'
          })
        : null
    ]
  })
}

/**
 * One storefront card. The cover and title are one real button; the actions sit beside it, never
 * inside it, so a keyboard user meets two separate targets instead of nested controls. Hover and
 * focus are a rule change, not depth: the plate keeps `--cb-paper-raised`, its side rules take ink
 * and its base rule turns to the lamp. No shadow and no lift — the identity draws depth with rules
 * (H-152), and the mount settle is the only thing that moves.
 */
function WorkshopCard({ item, motion, index, shelfKey, onOpen, onInstall, busy, favorite, onFavorite, userCategory, layout }) {
  const [hover, setHover] = useState(false)
  const noteId = `cb-workshop-badge-${item.pack_id}`
  const settle = useCbSettle(motion, { beat: 'route', index, staggerMs: 40, enabled: index < CB_PATH_SETTLE_NODES })
  return jsxs('article', {
    'data-cb-workshop-card': item.pack_id,
    'data-cb-workshop-shelf': shelfKey || '',
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      minWidth: 0,
      padding: '0.65rem',
      border: `1px solid ${hover ? 'var(--cb-ink-soft)' : 'var(--cb-rule)'}`,
      borderRadius: '3px',
      background: 'var(--cb-paper-raised)',
      borderBottom: hover ? '2px solid var(--cb-lamp)' : '2px solid var(--cb-rule)',
      ...(settle || {})
    },
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    children: [
      jsxs('button', {
        type: 'button',
        'data-cb-workshop-open': item.pack_id,
        'aria-label': `Open the pack page for ${item.title}`,
        onClick: () => onOpen(item),
        onBlur: () => setHover(false),
        onFocus: () => setHover(true),
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: '0.45rem',
          padding: 0,
          border: 'none',
          background: 'none',
          textAlign: 'left',
          cursor: 'pointer',
          minWidth: 0,
          color: 'var(--cb-ink)',
          borderRadius: '2px'
        },
        children: [
          jsx(WorkshopCover, { item, layout, hero: false }),
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.lead,
              fontWeight: 600,
              lineHeight: 1.25,
              letterSpacing: '-0.005em',
              color: 'var(--cb-ink)',
              overflowWrap: 'anywhere'
            },
            children: item.title
          }),
          jsx('p', {
            style: {
              margin: 0,
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.meta,
              lineHeight: 1.45,
              color: 'var(--cb-ink-soft)',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden'
            },
            children: item.outcome
          }),
          jsx(WorkshopMeta, { item })
        ]
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.5rem', marginTop: 'auto' },
        children: [
          item.installed
            ? jsx(CbAction, {
                variant: 'secondary',
                onClick: () => onOpen(item, { continue: true }),
                'aria-label': `Continue ${item.title}`,
                children: 'Continue'
              })
            : jsx(CbAction, {
                variant: 'secondary',
                onClick: () => onInstall(item),
                disabled: busy,
                pending: busy,
                'aria-label': `Add ${item.title} to your library`,
                children: busy ? 'Adding…' : 'Add to library'
              }),
          jsx('button', {
            type: 'button',
            'data-cb-workshop-favorite': favorite ? 'on' : 'off',
            'aria-pressed': favorite ? 'true' : 'false',
            'aria-label': favorite ? `Remove ${item.title} from favourites` : `Favourite ${item.title}`,
            onClick: () => onFavorite(item),
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.25rem',
              minWidth: '44px',
              minHeight: '44px',
              border: '1px solid var(--cb-rule)',
              borderRadius: '2px',
              background: 'var(--cb-paper)',
              color: favorite ? 'var(--cb-lamp)' : 'var(--cb-ink-soft)',
              cursor: 'pointer',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption
            },
            children: [
              jsx(sdk.Codicon, { name: favorite ? 'star-full' : 'star-empty', size: CB_ICON_UI }),
              jsx('span', { children: favorite ? 'Saved' : 'Save' })
            ]
          }),
          userCategory
            ? jsx('span', {
                'data-cb-workshop-user-category': userCategory,
                style: {
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.caption,
                  color: 'var(--cb-ink-soft)',
                  border: '1px solid var(--cb-rule)',
                  borderRadius: '999px',
                  padding: '0.1rem 0.45rem'
                },
                children: `Your shelf: ${userCategory}`
              })
            : null
        ]
      })
    ]
  })
}

function WorkshopHero({ item, layout, motion, onOpen, onInstall, busy }) {
  const settle = useCbSettle(motion, { beat: 'route', fromOpacity: 0.9, from: 'translateY(4px)' })
  const noteId = `cb-workshop-hero-badge`
  const wide = layout === 'wide' || layout === 'mid'
  return jsxs('section', {
    'data-cb-workshop-hero': item.pack_id,
    'aria-labelledby': 'cb-workshop-hero-title',
    style: {
      display: 'grid',
      gridTemplateColumns: wide ? 'minmax(0, 1.1fr) minmax(0, 0.9fr)' : 'minmax(0, 1fr)',
      gap: wide ? '1.75rem' : '1rem',
      alignItems: 'stretch',
      padding: wide ? '1.1rem' : '0.8rem',
      border: '1px solid var(--cb-rule)',
      borderRadius: '3px',
      background: 'var(--cb-paper-raised)',
      ...(settle || {})
    },
    children: [
      jsx(WorkshopCover, { item, layout, hero: true, caption: true }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.65rem', minWidth: 0, justifyContent: 'center' },
        children: [
          jsx('div', {
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--cb-ink-soft)'
            },
            children: 'Featured pack'
          }),
          jsx('h2', {
            id: 'cb-workshop-hero-title',
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.12,
              letterSpacing: '-0.01em',
              color: 'var(--cb-ink)',
              overflowWrap: 'anywhere'
            },
            children: item.title
          }),
          jsx('p', {
            style: {
              margin: 0,
              maxWidth: CB_MEASURE,
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.lead,
              lineHeight: 1.5,
              color: 'var(--cb-ink)'
            },
            children: item.outcome
          }),
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem 0.7rem' },
            children: [jsx(WorkshopBadge, { item, id: noteId }), jsx(WorkshopMeta, { item })]
          }),
          jsx(WorkshopTrustNote, { item, id: noteId }),
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.2rem' },
            children: [
              item.installed
                ? jsx(CbAction, {
                    variant: 'primary',
                    onClick: () => onOpen(item, { continue: true }),
                    children: 'Continue'
                  })
                : jsx(CbAction, {
                    variant: 'primary',
                    onClick: () => onInstall(item),
                    disabled: busy,
                    pending: busy,
                    children: busy ? 'Adding…' : 'Add to library'
                  }),
              jsx(CbAction, { variant: 'tertiary', onClick: () => onOpen(item), children: 'Read the pack page' })
            ]
          })
        ]
      })
    ]
  })
}

function WorkshopShelf({ title, caption, items, ...rest }) {
  return jsxs('section', {
    'data-cb-workshop-shelf-section': title,
    'aria-label': title,
    style: { display: 'flex', flexDirection: 'column', gap: '0.65rem', minWidth: 0 },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.25rem 0.75rem',
          paddingBottom: '0.35rem',
          borderBottom: '1px solid var(--cb-rule)'
        },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.2,
              color: 'var(--cb-ink)'
            },
            children: title
          }),
          caption
            ? jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: caption
              })
            : null
        ]
      }),
      jsx('div', {
        style: {
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 15rem), 1fr))',
          gap: '0.75rem',
          minWidth: 0
        },
        children: items.map((entry, index) =>
          jsx(WorkshopCard, { ...rest, item: entry, index, shelfKey: title }, entry.pack_id)
        )
      })
    ]
  })
}

function WorkshopDetail({ item, layout, motion, onBack, onInstall, onContinue, busy, favorite, onFavorite, userCategory, onCategory }) {
  const settle = useCbSettle(motion, { beat: 'route', fromOpacity: 0.94, from: 'translateY(3px)' })
  const noteId = `cb-workshop-detail-badge-${item.pack_id}`
  const headingRef = useRef(null)
  useEffect(() => {
    const node = headingRef.current
    if (node && typeof node.focus === 'function') node.focus({ preventScroll: true })
  }, [item.pack_id])
  const wide = layout === 'wide'
  return jsxs('article', {
    'data-cb-workshop-detail': item.pack_id,
    'aria-labelledby': 'cb-workshop-detail-title',
    style: { display: 'flex', flexDirection: 'column', gap: '1.1rem', minWidth: 0, ...(settle || {}) },
    children: [
      jsx('div', {
        children: jsx(CbAction, {
          variant: 'tertiary',
          onClick: onBack,
          'data-cb-workshop-back': '',
          children: '← All packs'
        })
      }),
      jsxs('div', {
        style: {
          display: 'grid',
          gridTemplateColumns: wide ? 'minmax(0, 0.82fr) minmax(0, 1.18fr)' : 'minmax(0, 1fr)',
          gap: wide ? '1.5rem' : '0.9rem',
          alignItems: 'start',
          minWidth: 0
        },
        children: [
          jsx(WorkshopCover, { item, layout, hero: true, caption: true }),
          jsxs('header', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.55rem', minWidth: 0 },
            children: [
              jsx('h2', {
                id: 'cb-workshop-detail-title',
                ref: headingRef,
                tabIndex: -1,
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.12,
                  letterSpacing: '-0.01em',
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere',
                  outline: 'none'
                },
                children: item.title
              }),
              jsx('p', {
                style: {
                  margin: 0,
                  maxWidth: CB_MEASURE,
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.lead,
                  lineHeight: 1.5,
                  color: 'var(--cb-ink)'
                },
                children: item.outcome
              }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem 0.7rem' },
                children: [jsx(WorkshopBadge, { item, id: noteId }), jsx(WorkshopMeta, { item })]
              }),
              jsx(WorkshopTrustNote, { item, id: noteId }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', paddingTop: '0.2rem' },
                children: [
                  item.installed
                    ? jsx(CbAction, { variant: 'primary', onClick: () => onContinue(item), children: 'Continue this course' })
                    : jsx(CbAction, {
                        variant: 'primary',
                        onClick: () => onInstall(item),
                        disabled: busy,
                        pending: busy,
                        children: busy ? 'Adding…' : 'Add to library'
                      }),
                  jsx(CbAction, {
                    variant: 'tertiary',
                    onClick: () => onFavorite(item),
                    'aria-pressed': favorite ? 'true' : 'false',
                    children: favorite ? 'Saved' : 'Save for later'
                  })
                ]
              })
            ]
          })
        ]
      }),
      jsxs('div', {
        style: {
          display: 'grid',
          gridTemplateColumns: wide ? 'minmax(0, 1.25fr) minmax(0, 0.75fr)' : 'minmax(0, 1fr)',
          gap: '1.5rem',
          alignItems: 'start',
          minWidth: 0
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '1.1rem', minWidth: 0 },
            children: [
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-sections-title',
                style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-sections-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.heading,
                      fontWeight: 600,
                      color: 'var(--cb-ink)'
                    },
                    children: 'What you work through'
                  }),
                  jsx('p', {
                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                    children: `${plural(item.objective_count, 'objective', 'objectives')} · ${plural(item.section_count, 'section', 'sections')} · ${workshopMinutes(item) || 'time not estimated'}`
                  }),
                  jsx('ol', {
                    'data-cb-workshop-sections': '',
                    style: { margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column' },
                    children: item.sections.map((section, index) =>
                      jsxs('li', {
                        style: {
                          display: 'grid',
                          gridTemplateColumns: '2rem minmax(0, 1fr) auto',
                          gap: '0.6rem',
                          alignItems: 'baseline',
                          padding: '0.55rem 0',
                          borderTop: index === 0 ? '1px solid var(--cb-rule)' : '1px solid var(--cb-rule)'
                        },
                        children: [
                          jsx('span', {
                            'aria-hidden': 'true',
                            style: {
                              fontFamily: CB_SERIF,
                              fontSize: CB_TYPE.lead,
                              fontWeight: 600,
                              color: 'var(--cb-ink-soft)',
                              fontVariantNumeric: 'tabular-nums'
                            },
                            children: String(index + 1).padStart(2, '0')
                          }),
                          jsxs('div', {
                            style: { display: 'flex', flexDirection: 'column', gap: '0.1rem', minWidth: 0 },
                            children: [
                              jsx('span', {
                                style: {
                                  fontFamily: CB_SANS,
                                  fontSize: CB_TYPE.body,
                                  fontWeight: 600,
                                  color: 'var(--cb-ink)',
                                  overflowWrap: 'anywhere'
                                },
                                children: section.title
                              }),
                              section.objective
                                ? jsx('span', {
                                    style: {
                                      fontFamily: CB_SANS,
                                      fontSize: CB_TYPE.caption,
                                      color: 'var(--cb-ink-soft)',
                                      overflowWrap: 'anywhere'
                                    },
                                    children: section.objective
                                  })
                                : null
                            ]
                          }),
                          jsx('span', {
                            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                            children: section.minutes ? `${section.minutes} min` : ''
                          })
                        ]
                      }, `${section.title}-${index}`)
                    )
                  })
                ]
              }),
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-not-title',
                style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-not-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.heading,
                      fontWeight: 600,
                      color: 'var(--cb-ink)'
                    },
                    children: 'What this course will not teach'
                  }),
                  jsx('ul', {
                    style: { margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' },
                    children: item.will_not_teach.map((line, index) =>
                      jsx('li', {
                        style: {
                          fontFamily: CB_SANS,
                          fontSize: CB_TYPE.body,
                          lineHeight: 1.55,
                          color: 'var(--cb-ink)',
                          overflowWrap: 'anywhere'
                        },
                        children: line
                      }, `not-${index}`)
                    )
                  })
                ]
              }),
              item.creator_note
                ? jsxs('section', {
                    'aria-labelledby': 'cb-workshop-note-title',
                    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
                    children: [
                      jsx('h3', {
                        id: 'cb-workshop-note-title',
                        style: {
                          margin: 0,
                          fontFamily: CB_SERIF,
                          fontSize: CB_TYPE.heading,
                          fontWeight: 600,
                          color: 'var(--cb-ink)'
                        },
                        children: 'From the creator'
                      }),
                      jsx('p', {
                        style: {
                          margin: 0,
                          maxWidth: CB_MEASURE,
                          fontFamily: CB_SANS,
                          fontSize: CB_TYPE.body,
                          lineHeight: 1.6,
                          color: 'var(--cb-ink)'
                        },
                        children: item.creator_note
                      })
                    ]
                  })
                : null
            ]
          }),
          jsxs('aside', {
            style: { display: 'flex', flexDirection: 'column', gap: '1.1rem', minWidth: 0 },
            children: [
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-facts-title',
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.4rem',
                  padding: '0.7rem 0.8rem',
                  background: 'var(--cb-paper-raised)',
                  border: '1px solid var(--cb-rule)',
                  borderRadius: '3px'
                },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-facts-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      fontWeight: 600,
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      color: 'var(--cb-ink-soft)'
                    },
                    children: 'Evidence and provenance'
                  }),
                  jsx('dl', {
                    style: { margin: 0, display: 'grid', gridTemplateColumns: 'auto minmax(0, 1fr)', gap: '0.3rem 0.7rem' },
                    children: workshopFactRows(item).map((fact) =>
                      [
                        jsx('dt', {
                          style: {
                            margin: 0,
                            fontFamily: CB_SANS,
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink-soft)'
                          },
                          children: fact.label
                        }, `dt-${fact.label}`),
                        jsx('dd', {
                          style: {
                            margin: 0,
                            fontFamily: CB_SANS,
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink)',
                            overflowWrap: 'anywhere'
                          },
                          children: fact.value
                        }, `dd-${fact.label}`)
                      ]
                    )
                  })
                ]
              }),
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-license-title',
                style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-license-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.lead,
                      fontWeight: 600,
                      color: 'var(--cb-ink)'
                    },
                    children: 'Licence and attribution'
                  }),
                  jsx('p', {
                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                    children: `${item.license.id}${item.license.redistribution ? ` · ${item.license.redistribution.replace('_', ' ')}` : ''}`
                  }),
                  item.license.note
                    ? jsx('p', {
                        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                        children: item.license.note
                      })
                    : null,
                  item.attribution
                    ? jsx('p', {
                        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                        children: item.attribution
                      })
                    : null
                ]
              }),
              item.sources.length
                ? jsxs('section', {
                    'aria-labelledby': 'cb-workshop-sources-title',
                    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
                    children: [
                      jsx('h3', {
                        id: 'cb-workshop-sources-title',
                        style: {
                          margin: 0,
                          fontFamily: CB_SERIF,
                          fontSize: CB_TYPE.lead,
                          fontWeight: 600,
                          color: 'var(--cb-ink)'
                        },
                        children: 'Sources'
                      }),
                      jsx('ul', {
                        style: { margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                        children: item.sources.map((source, index) =>
                          jsxs('li', {
                            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink)' },
                            children: [
                              source.url
                                ? jsx('a', {
                                    href: source.url,
                                    target: '_blank',
                                    rel: 'noreferrer noopener',
                                    style: { color: 'var(--cb-accent)' },
                                    children: source.title
                                  })
                                : jsx('span', { children: source.title }),
                              source.publisher ? jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: ` — ${source.publisher}` }) : null,
                              source.license_note
                                ? jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: source.license_note })
                                : null
                            ]
                          }, `source-${index}`)
                        )
                      })
                    ]
                  })
                : null,
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-version-title',
                style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-version-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.lead,
                      fontWeight: 600,
                      color: 'var(--cb-ink)'
                    },
                    children: 'Version history'
                  }),
                  jsx('ol', {
                    style: { margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.45rem' },
                    children: item.changelog.map((entry) =>
                      jsxs('li', {
                        style: { display: 'flex', flexDirection: 'column', gap: '0.05rem' },
                        children: [
                          jsx('span', {
                            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink)' },
                            children: `v${entry.version}${entry.date ? ` · ${entry.date}` : ''}`
                          }),
                          jsx('span', {
                            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                            children: entry.note
                          })
                        ]
                      }, `version-${entry.version}`)
                    )
                  }),
                  jsx('p', {
                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
                    children: `Content hash ${item.content_hash}`
                  })
                ]
              }),
              jsxs('section', {
                'aria-labelledby': 'cb-workshop-shelf-title',
                style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                children: [
                  jsx('h3', {
                    id: 'cb-workshop-shelf-title',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.lead,
                      fontWeight: 600,
                      color: 'var(--cb-ink)'
                    },
                    children: 'Your shelf'
                  }),
                  jsx('p', {
                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: 'A bookmark on this device. The pack’s own categories stay as they are.'
                  }),
                  jsx('div', {
                    style: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem' },
                    children: WORKSHOP_USER_CATEGORIES.map((category) =>
                      jsx('button', {
                        type: 'button',
                        'data-cb-workshop-category': category,
                        'aria-pressed': userCategory === category ? 'true' : 'false',
                        onClick: () => onCategory(item, userCategory === category ? null : category),
                        style: {
                          minHeight: '44px',
                          padding: '0.25rem 0.6rem',
                          fontFamily: CB_SANS,
                          fontSize: CB_TYPE.caption,
                          fontWeight: userCategory === category ? 600 : 400,
                          color: 'var(--cb-ink)',
                          background: userCategory === category ? 'var(--cb-lamp-soft)' : 'var(--cb-paper)',
                          border: `1px solid ${userCategory === category ? 'var(--cb-lamp)' : 'var(--cb-rule)'}`,
                          borderRadius: '999px',
                          cursor: 'pointer'
                        },
                        children: category
                      }, category)
                    )
                  })
                ]
              })
            ]
          })
        ]
      })
    ]
  })
}

/** The facts a pack page may print. Each row is a recorded value or it is absent. */
function workshopFactRows(item) {
  const rows = []
  rows.push({ label: 'Content hash', value: item.content_hash })
  rows.push({
    label: 'Integrity',
    value: item.integrity.hashes_match
      ? `Every file matches the manifest (${plural(item.integrity.file_count, 'file', 'files')}, ${workshopFileSize(item.integrity.expanded_bytes)})`
      : 'Hashes did not match when this pack was read'
  })
  rows.push({
    label: 'Automated checks',
    value: item.trust_labels.indexOf('automated_checks_passed') >= 0 ? 'Passed' : 'Not recorded'
  })
  rows.push({
    label: 'Human review',
    value: item.trust_labels.indexOf('human_review_recorded') >= 0 ? 'Recorded' : 'None recorded'
  })
  rows.push({
    label: 'Model support',
    value: item.trust_labels.indexOf('model_assessed_support') >= 0 ? 'Sources judged by a model, not a person' : 'None recorded'
  })
  rows.push({ label: 'Provenance', value: `${item.recipe} recipe · ${item.locale || 'no locale declared'}` })
  if (item.installed && item.installed.evidence_summary) {
    const summary = item.installed.evidence_summary
    rows.push({
      label: 'Your evidence',
      value: `${summary.independent} of ${summary.total_objectives} objectives have independent evidence${summary.review_due ? ` · ${summary.review_due} due` : ''}`
    })
  }
  return rows
}

function WorkshopDiscover({ catalog, layout, motion, prefs, onOpen, onInstall, busyInstall, onFavorite, onOpenCourse }) {
  const [filter, setFilter] = useState('all')
  const items = catalog.items || []
  const favoriteSet = new Set(prefs.favorites)
  const featured = items.find((item) => item.pack_id === catalog.featured_pack_id) || items[0]
  const categories = []
  for (const item of items) {
    for (const category of item.categories || []) {
      if (categories.indexOf(category) < 0) categories.push(category)
    }
  }
  const shown = filter === 'all' ? items : items.filter((item) => (item.categories || []).indexOf(filter) >= 0)
  const savedItems = items.filter((item) => favoriteSet.has(item.pack_id) || (prefs.categories || {})[item.pack_id])
  // Shelves follow each pack's own first category, in catalogue order. The catalogue is the
  // taxonomy: this surface never invents a shelf a pack does not already belong to, and the
  // filter pills above are drawn from the same field.
  const shelves = []
  if (filter === 'all') {
    const order = []
    for (const item of items) {
      const name = (item.categories || [])[0] || 'Other packs'
      if (order.indexOf(name) < 0) order.push(name)
    }
    for (const name of order) {
      shelves.push({
        title: name,
        items: items.filter((item) => ((item.categories || [])[0] || 'Other packs') === name)
      })
    }
  } else {
    shelves.push({ title: filter, items: shown })
  }
  const shelfKey = `${filter}-${shown.map((item) => item.pack_id).join(',')}`
  const cardProps = {
    motion,
    layout,
    onOpen,
    onInstall,
    busy: null,
    onFavorite,
    onOpenCourse
  }
  return jsxs('div', {
    'data-cb-workshop-discover': '',
    style: { display: 'flex', flexDirection: 'column', gap: '1.5rem', minWidth: 0 },
    children: [
      featured
        ? jsx(WorkshopHero, { item: featured, layout, motion, onOpen, onInstall, onContinue: onOpenCourse, busy: busyInstall === featured.pack_id })
        : null,
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.5rem 1rem'
        },
        children: [
          jsx('h2', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              color: 'var(--cb-ink)'
            },
            children: 'Find a pack',
          }),
          jsxs('div', {
            'data-cb-workshop-filter': '',
            role: 'group',
            'aria-label': 'Filter packs by category',
            style: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem' },
            children: [
              jsx('button', {
                type: 'button',
                'aria-pressed': filter === 'all' ? 'true' : 'false',
                onClick: () => setFilter('all'),
                style: workshopFilterStyle(filter === 'all'),
                children: 'All'
              })
            ].concat(
              categories.map((category) =>
                jsx('button', {
                  type: 'button',
                  'aria-pressed': filter === category ? 'true' : 'false',
                  onClick: () => setFilter(category),
                  style: workshopFilterStyle(filter === category),
                  children: category
                }, category)
              )
            )
          })
        ]
      }),
      filter === 'all' && savedItems.length
        ? jsx(WorkshopShelf, {
            ...cardProps,
            title: 'Your shelf',
            caption: 'Saved or labelled on this device',
            items: savedItems
          })
        : null,
      ...shelves.map((shelf) =>
        jsx(WorkshopShelf, {
          ...cardProps,
          title: shelf.title,
          caption: plural(shelf.items.length, 'pack', 'packs'),
          items: shelf.items
        }, `${shelfKey}-${shelf.title}`)
      )
    ]
  })
}

function workshopFilterStyle(selected) {
  return {
    minHeight: '44px',
    padding: '0.25rem 0.7rem',
    fontFamily: CB_SANS,
    fontSize: CB_TYPE.caption,
    fontWeight: selected ? 600 : 400,
    color: selected ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
    background: selected ? 'var(--cb-lamp-soft)' : 'transparent',
    border: `1px solid ${selected ? 'var(--cb-lamp)' : 'var(--cb-rule)'}`,
    borderRadius: '999px',
    cursor: 'pointer'
  }
}

/** The imported-pack ledger: what this profile holds, at which version, from where. */
function WorkshopProvenance({ implemented, motion, layout }) {
  const payload = { filter: 'all', limit: 100 }
  const key = JSON.stringify(payload)
  const { status, data, error, stale, reload } = useRpcQuery('pack.list', payload, key, backendSupports('pack.list'))
  const [selected, setSelected] = useState(null)
  const [preview, setPreview] = useState(null)
  const rows = data && Array.isArray(data.items) ? data.items : []
  const open = useCallback(async (row) => {
    setSelected(`${row.pack_id}@${row.pack_version}`)
    setPreview(null)
    const response = await rpc('pack.inspect', { pack_id: row.pack_id, pack_version: row.pack_version })
    if (response && response.ok) setPreview(response.result)
    else setPreview({ error: (response && response.error) || { message: 'This pack could not be inspected.' } })
  }, [])
  return jsxs('div', {
    'data-cb-workshop-provenance': '',
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: CB_MEASURE, minWidth: 0 },
    children: [
      jsx(PlateHead, {
        title: 'The Workshop ledger',
        label: 'Imported and shared packs',
        caption:
          'Every pack this profile holds, the version it was imported at, where it came from and the hash that was verified. There is no publishing, no upload and no version the backend did not record.'
      }),
      jsx('p', {
        id: 'cb-workshop-ledger-note',
        style: {
          margin: 0,
          maxWidth: CB_MEASURE,
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.caption,
          lineHeight: 1.5,
          color: 'var(--cb-ink-soft)'
        },
        children:
          'A row is a recorded import, not a verdict: it names the version, the source and the hash this profile verified at import. Inspecting a row re-hashes the pack now. No row claims a human review.'
      }),
      status === 'loading' && !data
        ? jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the pack ledger' }) })
        : status === 'error' && !data
          ? jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
              children: [
                jsx(EmptyState, {
                  title: 'The pack ledger could not be read',
                  description: `${(error && error.code) || 'HOST_UNAVAILABLE'}: ${describeError(error)}`
                }),
                jsx(CbAction, { variant: 'tertiary', onClick: reload, className: 'self-start', children: 'Try again' })
              ]
            })
          : rows.length === 0
            ? jsx(EmptyState, {
                title: 'No packs on this profile yet',
                description:
                  'Add a pack from Discover, or import one from a file in the Library tab. This ledger then records exactly what arrived.'
              })
            : jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.5rem', minWidth: 0 },
                children: [
                  stale
                    ? jsx('p', {
                        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: 'Reconnecting. Showing the last pack ledger read.'
                      })
                    : null,
                  rows.map((row) => {
                    const rowKey = `${row.pack_id}@${row.pack_version}`
                    const current = selected === rowKey
                    return jsxs('article', {
                      'data-cb-workshop-ledger-row': rowKey,
                      style: {
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.3rem',
                        padding: '0.6rem 0.7rem',
                        border: `1px solid ${current ? 'var(--cb-accent)' : 'var(--cb-rule)'}`,
                        borderRadius: '3px',
                        background: current ? 'var(--cb-accent-soft)' : 'var(--cb-paper-raised)',
                        minWidth: 0
                      },
                      children: [
                        jsxs('div', {
                          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.3rem 0.6rem' },
                          children: [
                            jsx('h3', {
                              style: {
                                margin: 0,
                                fontFamily: CB_SERIF,
                                fontSize: CB_TYPE.lead,
                                fontWeight: 600,
                                color: 'var(--cb-ink)',
                                overflowWrap: 'anywhere'
                              },
                              children: `${row.pack_id} · v${row.pack_version}`
                            }),
                            jsx('span', {
                              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                              children: `${row.state} · ${row.source} · ${plural(row.file_count, 'file', 'files')}`
                            })
                          ]
                        }),
                        jsx('p', {
                          style: {
                            margin: 0,
                            fontFamily: CB_SANS,
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink-soft)',
                            overflowWrap: 'anywhere'
                          },
                          children: `${row.license && row.license.id ? row.license.id : 'licence unspecified'} · ${row.content_hash}`
                        }),
                        current && preview
                          ? preview.error
                            ? jsx('p', {
                                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-coral)' },
                                children: `Inspection refused: ${describeError(preview.error)}`
                              })
                            : jsxs('div', {
                                'data-cb-workshop-ledger-preview': '',
                                style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
                                children: [
                                  jsx('p', {
                                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink)' },
                                    children: preview.integrity.hashes_match
                                      ? 'Integrity verified now: every declared file matches its hash.'
                                      : 'Hashes do not match now; the pack drifted from its manifest.'
                                  }),
                                  jsx('p', {
                                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                                    children: `Trust labels: ${(preview.trust.labels || []).join(', ') || 'none recorded'}`
                                  })
                                ]
                              })
                          : jsx(CbAction, {
                              variant: 'tertiary',
                              className: 'self-start',
                              onClick: () => open(row),
                              'aria-expanded': current ? 'true' : 'false',
                              children: current ? 'Re-check the pack' : 'Inspect this version',
                              'aria-label': `Inspect ${row.pack_id} version ${row.pack_version}`
                            })
                      ]
                    }, rowKey)
                  })
                ]
              })
    ]
  })
}

/**
 * The destination. Three surfaces, one read of the catalogue, and the Library tab is the same
 * installed-pack shelf and import flow the route already had — moved under the Workshop so there is
 * one shelf, not two.
 */
function WorkshopView({ implemented, createOpen, onOpenCourse, onStartSyllabus, onStartImport, canSyllabus, canImport, onEmptyChange }) {
  const [tab, setTab] = useState('discover')
  const [selectedId, setSelectedId] = useState(null)
  const [installBusy, setInstallBusy] = useState(null)
  const [notice, setNotice] = useState(null)
  const width = useCbViewportWidth()
  const layout = cbLayoutFor(width)
  const motion = useCbMotion()
  const [prefs, toggleFavorite, setCategory] = useCbWorkshopPrefs()
  const catalog = useWorkshopCatalog(true)
  const items = catalog.data && Array.isArray(catalog.data.items) ? catalog.data.items : []
  const selected = selectedId ? items.find((item) => item.pack_id === selectedId) || null : null

  const onOpen = useCallback((item, options) => {
    if (options && options.continue) {
      openInstalled(item)
      return
    }
    setSelectedId(item.pack_id)
  }, [])

  const back = useCallback(() => {
    const packId = selectedId
    setSelectedId(null)
    if (!packId || typeof document === 'undefined') return
    window.setTimeout(() => {
      const node = document.querySelector(`[data-cb-workshop-open="${packId}"]`)
      if (node && typeof node.focus === 'function') node.focus({ preventScroll: true })
    }, 0)
  }, [selectedId])

  const openInstalled = useCallback(
    async (item) => {
      const courseId = item && item.installed && item.installed.course_id
      if (!courseId) {
        setNotice({ kind: 'warning', message: 'That pack is not in your library yet.' })
        return
      }
      const response = await rpc('library.list', { filter: 'all', limit: 100, sort: 'recent' })
      const rows = response && response.ok && response.result && Array.isArray(response.result.items) ? response.result.items : []
      const row = rows.find((candidate) => candidate.course_id === courseId)
      if (!row) {
        setNotice({ kind: 'warning', message: 'The library row for this pack could not be read. Reload the Library tab.' })
        return
      }
      setNotice(null)
      onOpenCourse(row)
    },
    [onOpenCourse]
  )

  const install = useCallback(
    async (item) => {
      setInstallBusy(item.pack_id)
      setNotice(null)
      try {
        const response = await rest('/workshop/install', { method: 'POST', body: { pack_id: item.pack_id } })
        if (!response || response.ok !== true) {
          setNotice({
            kind: 'warning',
            message: `${(response && response.code) || 'WORKSHOP_REFUSED'}: ${(response && response.message) || 'The pack could not be added.'}`
          })
          return
        }
        setNotice({
          kind: 'success',
          packId: item.pack_id,
          title: item.title,
          courseId: response.course_id,
          imported: response.imported,
          message: response.imported
            ? 'Added to your library. The course is open in Courses and the pack is installed on this profile.'
            : response.message || 'This pack is already in your library; nothing was imported twice.'
        })
        catalog.reload()
      } catch (error) {
        setNotice({ kind: 'warning', message: `HOST_UNAVAILABLE: ${describeError(error)}` })
      } finally {
        setInstallBusy(null)
      }
    },
    [catalog]
  )

  const onFavorite = useCallback(
    (item) => {
      toggleFavorite(item.pack_id)
    },
    [toggleFavorite]
  )

  const onCategory = useCallback(
    (item, category) => {
      setCategory(item.pack_id, category)
    },
    [setCategory]
  )

  let body
  if (tab === 'library') {
    body = jsxs('div', {
      'data-cb-workshop-library': '',
      style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: 0 },
      children: [
        jsxs('div', {
          'data-cb-workshop-library-actions': '',
          style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'flex-end' },
          children: [
            canSyllabus
              ? jsx(CbAction, { variant: 'secondary', onClick: onStartSyllabus, children: SYLLABUS_COPY.action })
              : null,
            canImport
              ? jsx(CbAction, { variant: 'primary', onClick: onStartImport, children: 'Import pack' })
              : null
          ]
        }),
        jsx(LibraryView, {
          implemented,
          createOpen,
          onOpen: onOpenCourse,
          onStartSyllabus,
          onStartImport,
          onEmptyChange
        })
      ]
    })
  } else if (tab === 'provenance') {
    body = jsx(WorkshopProvenance, { implemented, motion, layout })
  } else if (selected) {
    body = jsx(WorkshopDetail, {
      item: selected,
      layout,
      motion,
      onBack: back,
      onInstall: install,
      onContinue: openInstalled,
      busy: installBusy === selected.pack_id,
      favorite: prefs.favorites.indexOf(selected.pack_id) >= 0,
      onFavorite,
      userCategory: (prefs.categories || {})[selected.pack_id] || null,
      onCategory
    })
  } else if (catalog.status === 'loading' && !catalog.data) {
    body = jsx('div', { className: 'py-8', children: jsx(sdk.Loader, { label: 'Reading the Workshop catalogue' }) })
  } else if (catalog.status === 'error') {
    body = jsxs('div', {
      'data-cb-workshop-error': (catalog.error && catalog.error.code) || 'WORKSHOP_UNAVAILABLE',
      style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', maxWidth: CB_MEASURE },
      children: [
        jsx('h2', {
          style: workshopStateHeadingStyle,
          children: 'The Workshop could not be read'
        }),
        jsx('p', {
          style: workshopStateBodyStyle,
          children: `${(catalog.error && catalog.error.code) || 'WORKSHOP_UNAVAILABLE'}: ${(catalog.error && catalog.error.message) || 'The catalogue did not answer.'}`
        }),
        jsx(CbAction, { variant: 'tertiary', onClick: catalog.reload, className: 'self-start', children: 'Try again' })
      ]
    })
  } else if (!items.length) {
    body = jsxs('div', {
      'data-cb-workshop-empty': '',
      style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', maxWidth: CB_MEASURE },
      children: [
        jsx('h2', { style: workshopStateHeadingStyle, children: 'No packs in this build' }),
        jsx('p', {
          style: workshopStateBodyStyle,
          children:
            'The Workshop ships with the packs this build bundles. If the catalogue is empty, nothing was installed and no pack is being offered.'
        })
      ]
    })
  } else {
    body = jsx(WorkshopDiscover, {
      catalog: catalog.data,
      layout,
      motion,
      prefs,
      onOpen,
      onInstall: install,
      busyInstall: installBusy,
      onFavorite,
      onOpenCourse: openInstalled
    })
  }

  return jsxs('div', {
    'data-cb-workshop': tab,
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
    children: [
      jsx('nav', {
        'data-cb-workshop-tabs': '',
        'aria-label': 'Workshop surfaces',
        style: { display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1.25rem', borderBottom: '1px solid var(--cb-rule)' },
        children: WORKSHOP_TABS.map((entry) =>
          jsx('button', {
            type: 'button',
            'data-cb-workshop-tab': entry.id,
            'aria-current': tab === entry.id ? 'page' : undefined,
            onClick: () => {
              setTab(entry.id)
              setSelectedId(null)
            },
            style: {
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${tab === entry.id ? 'var(--cb-lamp)' : 'transparent'}`,
              padding: '0.5rem 0',
              minHeight: '44px',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.meta,
              fontWeight: tab === entry.id ? 600 : 400,
              color: tab === entry.id ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
              cursor: tab === entry.id ? 'default' : 'pointer'
            },
            children: entry.label
          }, entry.id)
        )
      }),
      catalog.data && catalog.data.refused && catalog.data.refused.length
        ? jsxs('div', {
            'data-cb-workshop-refused': '',
            role: 'status',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              padding: '0.5rem 0.65rem',
              border: '1px solid var(--cb-coral)',
              borderRadius: '3px',
              background: 'var(--cb-paper-raised)'
            },
            children: [
              jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-coral)' },
                children: `${plural(catalog.data.refused.length, 'pack', 'packs')} could not be verified and are not shown`
              }),
              ...catalog.data.refused.map((entry) =>
                jsx('p', {
                  style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
                  children: `${entry.pack_id}: ${entry.reason}`
                }, `refused-${entry.pack_id}`)
              )
            ]
          })
        : null,
      notice
        ? jsxs('div', {
            'data-cb-workshop-notice': notice.kind,
            role: 'status',
            'aria-live': 'polite',
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.5rem',
              padding: '0.65rem 0.8rem',
              border: `1px solid ${notice.kind === 'success' ? 'var(--cb-field)' : 'var(--cb-coral)'}`,
              borderRadius: '3px',
              background: 'var(--cb-paper-raised)'
            },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0 },
                children: [
                  jsx('p', {
                    style: {
                      margin: 0,
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.meta,
                      fontWeight: 600,
                      color: notice.kind === 'success' ? 'var(--cb-field)' : 'var(--cb-coral)'
                    },
                    children: notice.kind === 'success' ? `Added: ${notice.title}` : 'Not added'
                  }),
                  jsx('p', {
                    style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: notice.message
                  })
                ]
              }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' },
                children: [
                  notice.courseId
                    ? jsx(CbAction, {
                        variant: 'secondary',
                        onClick: () => {
                          const item = items.find((entry) => entry.pack_id === notice.packId)
                          if (item) openInstalled(item)
                        },
                        children: 'Open the course'
                      })
                    : null,
                  jsx(CbAction, { variant: 'tertiary', onClick: () => setNotice(null), children: 'Dismiss' })
                ]
              })
            ]
          })
        : null,
      body
    ]
  })
}


