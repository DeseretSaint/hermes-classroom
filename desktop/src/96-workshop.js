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
  { id: 'provenance', label: 'Provenance' },
  { id: 'share', label: 'Share to store' }
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
  // A real artifact always wins. With no ready artifact the approved field_atlas@3 display cover
  // for this pack is the plate (D-007), so a mapped pack never falls back to a typographic cover.
  // `cb3KitCoverFor` answers the full asset key; `cb3Asset` is the one lookup that reads it.
  const kit = image ? null : cb3KitCoverFor(item)
  const kitImage = kit ? cb3KitSource(kit.id3x2) : null
  const ratio = hero ? '16 / 9' : '3 / 2'
  const alt = (cover.alt && String(cover.alt)) || (item && item.title) || 'Pack cover'
  const failed = cover.kind === 'artifact' && preview.state === 'text'
  return jsxs('figure', {
    'data-cb-workshop-cover': (item && item.pack_id) || 'none',
    'data-cb-workshop-cover-kind': image ? 'artifact' : kitImage ? 'kit' : 'typographic',
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
            : kitImage
            ? jsx('img', {
                alt,
                src: kitImage,
                loading: hero ? 'eager' : 'lazy',
                'data-cb-workshop-cover-image': '',
                'data-cb-workshop-cover-plate': kit.id3x2.split('.').pop(),
                style: {
                  display: 'block',
                  width: '100%',
                  height: '100%',
                  // A display plate is mechanically cropped into its box, on the hero band as
                  // well as on a store card; the pack never gets a letter standing in for art.
                  objectFit: 'cover',
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
          jsx(WorkshopCover, { item, layout, hero: false }, 'cover'),
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
          }, 'title'),
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
          }, 'outcome'),
          jsx(WorkshopMeta, { item }, 'meta')
        ]
      }, 'open'),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.5rem', marginTop: 'auto' },
        children: [
          item.installed
            ? jsx(CbAction, {
                variant: 'secondary',
                onClick: () => onOpen(item, { continue: true }),
                'aria-label': `Continue ${item.title}`,
                children: 'Continue'
              }, 'install')
            : jsx(CbAction, {
                variant: 'secondary',
                onClick: () => onInstall(item),
                disabled: busy,
                pending: busy,
                'aria-label': `Add ${item.title} to your library`,
                children: busy ? 'Adding…' : 'Add to library'
              }, 'install'),
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
              jsx(sdk.Codicon, { name: favorite ? 'star-full' : 'star-empty', size: CB_ICON_UI }, 'icon'),
              jsx('span', { children: favorite ? 'Saved' : 'Save' }, 'word')
            ]
          }, 'favorite'),
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
              }, 'shelf')
            : null
        ]
      }, 'actions')
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

/* ── CP-021 · Discover v3 (R-DISC) ───────────────────────────────────────────────────────────
 * The Store tab, rebuilt on the Field Atlas v3 primitives: one page head, the H-196 tabs, a
 * featured plate whose quiet field and grid share **one** track, a collectible grid whose column
 * count is measured against the route (never the window), and the fox at the grid's foot inside
 * its safe area.
 *
 * Honesty rules (SPEC-V3 §6):
 *   - every card is one metadata pattern: subject chip, real section count, one trust label that
 *     comes from `pack.inspect.trust.labels`; no star, no review count, no badge word that has no
 *     backing field;
 *   - the banner title and line are the pack manifest's own title and the catalogue's outcome;
 *   - a pack's cover is the pack's own artifact through `/media/:id`; with no artifact the plate
 *     is typographic and no shape is drawn to stand in for art;
 *   - exactly one filled control on the surface: `Preview this pack` on the banner.
 *
 * The banner's quiet field is a paper field **beside** the art, not a scrim over it. The CP-013
 * `discover-banner` scene has no media route yet (it is a shipped master, not a pack artifact), so
 * the plate is composed from the featured pack's real cover artifact; when that has no route the
 * quiet field takes the full width and no art is invented.
 */
const CB3_DISCOVER_COPY = Object.freeze({
  title: 'Discover',
  sub: 'Packs you can learn from, already on this device.',
  shelfTitle: 'All packs',
  primary: 'Preview this pack',
  loading: 'Reading your workshop.',
  emptyTitle: 'No packs on this device',
  emptyBody: 'A pack file you add shows up here.',
  emptyAction: 'Import a pack',
  errorTitle: 'The workshop could not be read',
  errorBody: 'Packs you already have are unchanged. Try again.',
  errorAction: 'Try again',
  offlineTitle: 'You are offline',
  offlineBody: 'Packs already on this device still list. The rest waits.',
  offlineAction: 'Try again',
  rejectedAction: 'Open Provenance'
})

/** The four trust labels, in the order they are shown; the word is the deck's, not a claim. */
const CB3_TRUST_LABELS = Object.freeze([
  Object.freeze({ id: 'integrity_verified', label: 'Files checked' }),
  Object.freeze({ id: 'automated_checks_passed', label: 'Automated checks passed' }),
  Object.freeze({ id: 'human_review_recorded', label: 'Human review recorded' }),
  Object.freeze({ id: 'model_assessed_support', label: 'Support assessed by a model' })
])

function cb3PackTrustLabels(item) {
  const labels = Array.isArray(item && item.trust_labels) ? item.trust_labels : []
  return CB3_TRUST_LABELS.filter((row) => labels.indexOf(row.id) >= 0)
}

function cb3PackSections(item) {
  const count = Number(item && item.section_count)
  return Number.isFinite(count) && count > 0 ? Math.round(count) : null
}

/** A pack's subject line is its own first catalogue category, never an invented chip word. */
function cb3PackSubject(item) {
  const categories = Array.isArray(item && item.categories) ? item.categories : []
  for (const category of categories) {
    if (typeof category === 'string' && category.trim()) return category
  }
  return null
}

/**
 * One cover resolver for the Store card, the pack detail and the Library tab's same row.
 *
 * A pack's own cover artifact always wins. When it has none — or its bytes have not arrived yet —
 * the approved field_atlas@3 display cover for that pack is the plate (D-007), so no pack ever
 * resolves to a typographic cover. The plate id comes from `cb3KitCoverFor`, which already answers
 * the full `cb.asset.kit.field_atlas.*` asset key; `cb3Asset` is the one lookup that reads it.
 */
function cb3PackCover(item) {
  const cover = (item && item.cover) || {}
  const artifactId = cover.kind === 'artifact' && typeof cover.artifact_id === 'string' ? cover.artifact_id : null
  const kit = cb3KitCoverFor(item)
  return {
    artifactId,
    title: (item && item.title) || 'Untitled pack',
    kitSrc: kit ? cb3KitSource(kit.id3x2) : null
  }
}

/**
 * Columns are a function of the **route** width (SPEC-V3 §3.3): 4 at 1000+, 3 from 620 to 999,
 * and 1 row at compact. Never `vw`, never the Desktop window.
 */
function cb3DiscoverColumns(routeWidth) {
  const width = Number(routeWidth)
  if (!Number.isFinite(width) || width <= 0) return 4
  if (width >= 1000) return 4
  if (width >= 620) return 3
  return 1
}

function cb3DiscoverFoxBox(routeWidth) {
  return Number(routeWidth) >= 1000 ? 96 : 88
}

const CB3_DISCOVER_HEADING = Object.freeze({
  margin: 0,
  fontFamily: 'var(--cb3-font-display)',
  fontSize: cb3Type('heading'),
  lineHeight: cb3Lead('heading'),
  fontWeight: 600,
  maxWidth: '34ch',
  overflowWrap: 'anywhere',
  color: cb3Role('ink')
})

const CB3_DISCOVER_BODY = Object.freeze({
  margin: 0,
  fontFamily: 'var(--cb3-font-ui)',
  fontSize: cb3Type('body'),
  lineHeight: cb3Lead('body'),
  color: cb3Role('ink-soft'),
  maxWidth: '52ch'
})

/** D2: the page head above the tabs. One h2 region; the page h1 is the route's own title. */
function WorkshopDiscoverHead({ line }) {
  return jsxs('header', {
    'data-cb3-discover-head': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: [
      jsx('h2', { style: CB3_DISCOVER_HEADING, children: CB3_DISCOVER_COPY.title }, 'title'),
      jsx('p', { style: CB3_DISCOVER_BODY, children: line || CB3_DISCOVER_COPY.sub }, 'sub')
    ]
  })
}

/**
 * D4 + D5: the featured plate. The left percentage is the reserved quiet field; the art sits in
 * its own region, mechanically cropped, never underneath the type. Card stock + `elev-1` is one
 * material object (the contract forbids a border and a shadow on the same object).
 */
function WorkshopDiscoverFeature({ item, layout, onOpen }) {
  const cover = cb3PackCover(item)
  const preview = useArtifactPreview(cover.artifactId)
  // A real artifact's bytes win; before they arrive, or when the pack has none, the approved
  // display cover is the plate (D-007). A pack never falls back to a typographic cover.
  const art = (cover.artifactId && preview.state === 'ready' ? preview.data_url : null) || cover.kitSrc
  const compact = layout.columns === 1
  const pad = layout.wide ? '2rem' : layout.columns === 3 ? '1.75rem' : '1.25rem'
  return jsxs('section', {
    'data-cb3-feature': item.pack_id,
    'aria-labelledby': 'cb3-feature-title',
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: compact ? 'column' : 'row',
      alignItems: 'stretch',
      width: '100%',
      minWidth: 0,
      minHeight: compact ? 0 : layout.wide ? '226px' : '213px',
      ...(compact ? {} : { aspectRatio: '4 / 1' }),
      overflow: 'hidden',
      borderRadius: cb3Radius('round'),
      backgroundColor: cb3Role('card-stock')
    },
    className: 'cb3-elev-1',
    children: [
      jsxs('div', {
        'data-cb3-quiet-field': '',
        style: {
          flex: compact ? '0 0 auto' : '0 0 40%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: '0.6rem',
          minWidth: 0,
          padding: pad
        },
        children: [
          jsx('h3', {
            id: 'cb3-feature-title',
            style: { ...CB3_DISCOVER_HEADING, fontSize: cb3Type('heading') },
            children: cover.title
          }, 'title'),
          item.outcome
            ? jsx('p', { style: { ...CB3_DISCOVER_BODY, maxWidth: '42ch' }, children: item.outcome }, 'outcome')
            : null,
          jsx('div', {
            style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem' },
            children: jsx(PillAction, {
              variant: 'primary',
              label: CB3_DISCOVER_COPY.primary,
              onClick: () => {
                if (typeof onOpen === 'function') onOpen(item)
              },
              'data-cb3-feature-primary': item.pack_id
            }, 'primary')
          }, 'actions')
        ]
      }, 'quiet'),
      art
        ? jsx('div', {
            'data-cb3-feature-art': item.pack_id,
            'aria-hidden': 'true',
            style: {
              position: 'relative',
              flex: compact ? '0 0 auto' : '1 1 auto',
              width: compact ? '100%' : undefined,
              height: compact ? '160px' : undefined,
              minWidth: 0,
              overflow: 'hidden'
            },
            children: jsx('img', {
              src: art,
              alt: '',
              style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover' }
            }, 'img')
          }, 'art')
        : null
    ]
  })
}

/** The one metadata row: real sections + one trust label, in the same order on every card. */
function cb3DiscoverMeta(item) {
  const sections = cb3PackSections(item)
  const trust = cb3PackTrustLabels(item)[0] || null
  const parts = []
  if (sections !== null) {
    parts.push(jsx('span', { children: `${sections} ${sections === 1 ? 'section' : 'sections'}` }, 'sections'))
  }
  if (sections !== null && trust) parts.push(jsx('span', { 'aria-hidden': 'true', children: '·' }, 'sep'))
  if (trust) {
    parts.push(
      jsxs('span', {
        'data-cb3-trust': trust.id,
        style: { display: 'inline-flex', alignItems: 'center', gap: '0.3rem' },
        children: [
          jsx(sdk.Codicon, { name: 'shield', size: CB_ICON_UI }, 'icon'),
          jsx('span', { children: trust.label }, 'label')
        ]
      }, 'trust')
    )
  }
  return parts.length ? parts : null
}

function cb3DiscoverOpenKey(event, item, onOpen) {
  if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return
  event.preventDefault()
  if (typeof onOpen === 'function') onOpen(item)
}

/** D7 at wide/mid: the collectible card, every card one paper object on the same track. */
function WorkshopDiscoverCard({ item, onOpen }) {
  const cover = cb3PackCover(item)
  const preview = useArtifactPreview(cover.artifactId)
  // A real artifact's bytes win; before they arrive, or when the pack has none, the approved
  // display cover is the plate (D-007). A pack never falls back to a typographic cover.
  const art = (cover.artifactId && preview.state === 'ready' ? preview.data_url : null) || cover.kitSrc
  const rejected = cb3PackTrustLabels(item).every((row) => row.id !== 'integrity_verified')
  return jsx(CollectibleCard, {
    'data-cb3-pack': item.pack_id,
    'data-cb3-pack-rejected': rejected ? 'true' : 'false',
    title: item.title,
    subject: cb3PackSubject(item),
    src: art,
    meta: cb3DiscoverMeta(item),
    role: 'link',
    tabIndex: 0,
    'aria-label': `Preview ${item.title}`,
    onClick: () => {
      if (typeof onOpen === 'function') onOpen(item)
    },
    onKeyDown: (event) => cb3DiscoverOpenKey(event, item, onOpen)
  }, item.pack_id)
}

/** D7 at compact: one pack per row, 88 × 59 art, text beside it. No card grid at 460. */
function WorkshopDiscoverRow({ item, onOpen }) {
  const cover = cb3PackCover(item)
  const preview = useArtifactPreview(cover.artifactId)
  // A real artifact's bytes win; before they arrive, or when the pack has none, the approved
  // display cover is the plate (D-007). A pack never falls back to a typographic cover.
  const art = (cover.artifactId && preview.state === 'ready' ? preview.data_url : null) || cover.kitSrc
  const subject = cb3PackSubject(item)
  return jsxs('article', {
    'data-cb3-pack': item.pack_id,
    'data-cb3-pack-layout': 'row',
    role: 'link',
    tabIndex: 0,
    'aria-label': `Preview ${item.title}`,
    onClick: () => {
      if (typeof onOpen === 'function') onOpen(item)
    },
    onKeyDown: (event) => cb3DiscoverOpenKey(event, item, onOpen),
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: '0.75rem',
      minWidth: 0,
      padding: '0.65rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      cursor: 'pointer'
    },
    children: [
      jsx('div', { style: { flex: '0 0 88px', width: '88px', minWidth: 0 }, children: jsx(CoverPlate3, { src: art, title: cover.title }) }, 'cover'),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0, flex: '1 1 auto' },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              fontWeight: 600,
              overflowWrap: 'anywhere'
            },
            children: cover.title
          }, 'title'),
          subject
            ? jsx('span', {
                'data-cb3-chip': 'subject',
                style: {
                  alignSelf: 'flex-start',
                  paddingInline: '0.5rem',
                  paddingBlock: '0.15rem',
                  borderRadius: cb3Radius('soft'),
                  backgroundColor: cb3Role('terracotta-quiet'),
                  color: cb3Role('ink'),
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('caption'),
                  lineHeight: cb3Lead('caption')
                },
                children: subject
              }, 'subject')
            : null,
          jsx('p', {
            style: {
              margin: 0,
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.3rem',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              color: cb3Role('ink-soft')
            },
            children: cb3DiscoverMeta(item)
          }, 'meta')
        ]
      }, 'text')
    ]
  }, item.pack_id)
}

function WorkshopDiscoverGrid({ items, layout, onOpen }) {
  const columns = layout.columns
  return jsx('div', {
    'data-cb3-discover-grid': String(columns),
    style: {
      display: 'grid',
      gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
      columnGap: columns === 1 ? '12px' : '16px',
      rowGap: columns === 1 ? '12px' : '24px',
      alignItems: 'stretch',
      width: '100%',
      minWidth: 0
    },
    children: items.map((item) =>
      columns === 1
        ? jsx(WorkshopDiscoverRow, { item, onOpen }, item.pack_id)
        : jsx(WorkshopDiscoverCard, { item, onOpen }, item.pack_id)
    )
  })
}

/** A quiet plate that keeps the banner's geometry for empty/error/offline. */
function WorkshopDiscoverNotice({ state, title, body, actionLabel, onAction }) {
  return jsxs('div', {
    'data-cb3-discover-state': state,
    style: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      gap: '0.6rem',
      width: '100%',
      minWidth: 0,
      minHeight: '226px',
      padding: '2rem',
      borderRadius: cb3Radius('round'),
      backgroundColor: cb3Role('card-stock')
    },
    className: 'cb3-elev-1',
    children: [
      jsx('h3', { style: CB3_DISCOVER_HEADING, children: title }, 'title'),
      jsx('p', { style: CB3_DISCOVER_BODY, children: body }, 'body'),
      actionLabel && typeof onAction === 'function'
        ? jsx('div', {
            style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem' },
            children: jsx(PillAction, { variant: 'quiet', label: actionLabel, onClick: onAction }, 'action')
          }, 'actions')
        : null
    ]
  })
}

/** Loading keeps the real region boxes; 40% card stock, no shimmer, no spinner. */
function WorkshopDiscoverSkeleton({ layout }) {
  const boxes = layout.columns * 2
  return jsxs('div', {
    'data-cb3-discover-skeleton': '',
    style: { display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', minWidth: 0 },
    children: [
      jsx('div', {
        'aria-hidden': 'true',
        style: {
          width: '100%',
          minHeight: '226px',
          borderRadius: cb3Radius('round'),
          backgroundColor: cb3Role('card-stock'),
          opacity: 0.4
        }
      }, 'banner'),
      jsx('div', {
        'aria-hidden': 'true',
        style: {
          display: 'grid',
          gridTemplateColumns: `repeat(${layout.columns}, minmax(0, 1fr))`,
          columnGap: layout.columns === 1 ? '12px' : '16px',
          rowGap: '24px'
        },
        children: Array.from({ length: boxes }, (unused, index) =>
          jsx('div', {
            style: {
              minHeight: layout.columns === 1 ? '76px' : '211px',
              borderRadius: cb3Radius('round'),
              backgroundColor: cb3Role('card-stock'),
              opacity: 0.4
            }
          }, `skeleton-${index}`)
        )
      }, 'grid')
    ]
  })
}

/**
 * The Discover body: head is painted by the destination shell above the tabs; this owns the
 * banner + shelf + grid and one state at a time. `refused` packs keep a quiet strip at the foot
 * (D9) and never disappear from the count they belong to.
 */
function WorkshopDiscoverV3({ items, featured, layout, status, error, refused, onOpen, onRetry, canImport, onImport, onOpenProvenance }) {
  const unique = []
  const seen = new Set()
  for (const item of items) {
    if (!item || !item.pack_id || seen.has(item.pack_id)) continue
    seen.add(item.pack_id)
    unique.push(item)
  }
  if (status === 'error') {
    const offline = Boolean(error && error.code === 'HOST_UNAVAILABLE')
    return jsx(WorkshopDiscoverNotice, {
      state: offline ? 'offline' : 'error',
      title: offline ? CB3_DISCOVER_COPY.offlineTitle : CB3_DISCOVER_COPY.errorTitle,
      body: offline ? CB3_DISCOVER_COPY.offlineBody : CB3_DISCOVER_COPY.errorBody,
      actionLabel: offline ? CB3_DISCOVER_COPY.offlineAction : CB3_DISCOVER_COPY.errorAction,
      onAction: onRetry
    })
  }
  if (!unique.length) {
    return jsx(WorkshopDiscoverNotice, {
      state: 'empty',
      title: CB3_DISCOVER_COPY.emptyTitle,
      body: CB3_DISCOVER_COPY.emptyBody,
      actionLabel: canImport ? CB3_DISCOVER_COPY.emptyAction : null,
      onAction: canImport ? onImport : null
    })
  }
  const featuredItem = featured || unique[0]
  const rejected = unique.filter((item) => cb3PackTrustLabels(item).every((row) => row.id !== 'integrity_verified'))
  return jsxs('div', {
    'data-cb3-discover-track': '',
    style: { display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', minWidth: 0 },
    children: [
      jsx(WorkshopDiscoverFeature, { item: featuredItem, layout, onOpen }, 'feature'),
      jsxs('section', {
        'data-cb3-discover-shelf': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%', minWidth: 0 },
        children: [
          jsxs('div', {
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              gap: '0.5rem 1rem'
            },
            children: [
              jsx('h2', {
                style: { ...CB3_DISCOVER_HEADING, fontSize: cb3Type('lead') },
                children: CB3_DISCOVER_COPY.shelfTitle
              }, 'title'),
              jsx('span', {
                'data-cb3-discover-count': '',
                style: {
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: cb3Lead('meta'),
                  color: cb3Role('ink-soft')
                },
                children: `${unique.length} ${unique.length === 1 ? 'pack' : 'packs'}`
              }, 'count')
            ]
          }, 'head'),
          jsx(WorkshopDiscoverGrid, { items: unique, layout, onOpen }, 'grid'),
          jsx('div', {
            'data-cb3-discover-fox': '',
            'aria-hidden': 'true',
            style: { display: 'flex', justifyContent: 'flex-end', width: '100%', minWidth: 0 },
            children: jsx(FoxPose, {
              pose: 'point',
              size: 128,
              style: { width: `${cb3DiscoverFoxBox(layout.routeWidth)}px`, height: `${cb3DiscoverFoxBox(layout.routeWidth)}px` }
            }, 'fox')
          }, 'fox'),
          rejected.length
            ? jsxs('div', {
                'data-cb3-discover-rejected': '',
                role: 'status',
                style: {
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.5rem',
                  minHeight: '48px',
                  padding: '0.5rem 0.75rem',
                  border: `1px solid ${cb3Role('rule')}`,
                  borderRadius: cb3Radius('soft'),
                  backgroundColor: cb3Role('card-stock')
                },
                children: [
                  jsx('p', {
                    style: {
                      margin: 0,
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('meta'),
                      lineHeight: cb3Lead('meta'),
                      color: cb3Role('alert')
                    },
                    children: rejected.map((item) => `${item.title} did not pass its checks.`).join(' ')
                  }, 'line'),
                  onOpenProvenance
                    ? jsx(PillAction, { variant: 'quiet', label: CB3_DISCOVER_COPY.rejectedAction, onClick: onOpenProvenance }, 'action')
                    : null
                ]
              })
            : null,
          refused && refused.length
            ? jsx('p', {
                'data-cb3-discover-refused': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('caption'),
                  lineHeight: cb3Lead('caption'),
                  color: cb3Role('ink-soft')
                },
                children: `${refused.length} ${refused.length === 1 ? 'pack' : 'packs'} could not be verified and are not shown.`
              })
            : null
        ]
      }, 'shelf')
    ]
  })
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
  // CP-021: the Discover composition is a function of the *route* width (SPEC-V3 §3.1/§3.3).
  // Columns: 4 wide, 3 mid, 1 row at compact. The fox box is 96 wide, 88 mid, absent compact.
  const discoverLayout = {
    routeWidth: width,
    columns: cb3DiscoverColumns(width),
    wide: !(width > 0) || width >= 1000
  }
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
  } else if (tab === 'share') {
    body = jsx(WorkshopShare, {})
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
    body = jsx(WorkshopDiscoverSkeleton, { layout: discoverLayout })
  } else {
    body = jsx(WorkshopDiscoverV3, {
      items,
      featured: items.find((item) => item.pack_id === catalog.data.featured_pack_id) || items[0] || null,
      layout: discoverLayout,
      status: catalog.status,
      error: catalog.error,
      refused: catalog.data && Array.isArray(catalog.data.refused) ? catalog.data.refused : [],
      onOpen,
      onRetry: catalog.reload,
      canImport: Boolean(canImport),
      onImport: onStartImport,
      onOpenProvenance: () => {
        setTab('provenance')
        setSelectedId(null)
      }
    })
  }

  return jsxs('div', {
    'data-cb-workshop': tab,
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
    children: [
      // D2 sits above the tabs; on the other two tabs the ledger and shelf carry their own head.
      tab === 'discover' && !selected
        ? jsx(WorkshopDiscoverHead, {
            line: catalog.status === 'loading' && !catalog.data ? CB3_DISCOVER_COPY.loading : null
          }, 'discover-head')
        : null,
      jsx('nav', {
        'data-cb-workshop-tabs': '',
        'aria-label': 'Workshop surfaces',
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
          gap: '0 1.5rem',
          borderBottom: `1px solid ${cb3Role('rule')}`
        },
        children: WORKSHOP_TABS.map((entry) =>
          jsx('button', {
            type: 'button',
            'data-cb-workshop-tab': entry.id,
            'data-cb-workshop-tab-active': tab === entry.id ? 'true' : 'false',
            'aria-current': tab === entry.id ? 'page' : undefined,
            onClick: () => {
              setTab(entry.id)
              setSelectedId(null)
            },
            style: {
              background: 'none',
              border: 'none',
              borderBottom: `3px solid ${tab === entry.id ? cb3Role('terracotta') : 'transparent'}`,
              padding: '0 0.1rem',
              minHeight: '44px',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              fontWeight: tab === entry.id ? 600 : 400,
              color: tab === entry.id ? cb3Role('ink') : cb3Role('ink-soft'),
              cursor: tab === entry.id ? 'default' : 'pointer'
            },
            children: entry.label
          }, entry.id)
        )
      }),
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




/** "1 objective", "2 objectives" — the shipped copy never ships a plural placeholder. */
function shareCount(value, noun) {
  return `${value} ${noun}${Number(value) === 1 ? '' : 's'}`
}

/**
 * The public decision, in the page's own modal language (the same centred card as
 * `ModeSwitchDialog`). Sharing is the one action that publishes: it opens a pull request on the
 * Coursebook repository and, when the author has no write access, forks that repository under
 * their GitHub account. The dialog names all three before the request carries `confirm: true`.
 */
function WorkshopShareConfirm({ item, onConfirm, onCancel }) {
  useEffect(() => {
    if (typeof document === 'undefined' || typeof document.addEventListener !== 'function') return undefined
    const onKey = (event) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return jsx('div', {
    'data-cb-workshop-share-confirm-backdrop': '',
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 70,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      background: 'color-mix(in srgb, var(--cb3-forest) 46%, transparent)'
    },
    onMouseDown: (event) => {
      if (event && event.target === event.currentTarget) onCancel()
    },
    children: jsxs('div', {
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'cb-workshop-share-confirm-title',
      'data-cb-workshop-share-confirm': item.enrollment_id,
      style: {
        width: '30rem',
        maxWidth: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem',
        padding: '1rem 1.1rem 1.1rem',
        background: cb3Role('card-stock'),
        border: `1px solid ${cb3Role('rule')}`,
        borderRadius: cb3Radius('round')
      },
      children: [
        jsx('h2', {
          id: 'cb-workshop-share-confirm-title',
          style: {
            margin: 0,
            fontFamily: 'var(--cb3-font-display)',
            fontSize: cb3Type('heading'),
            lineHeight: cb3Lead('heading'),
            fontWeight: 600,
            color: cb3Role('ink')
          },
          children: 'Publish this course?'
        }),
        jsx('p', {
          'data-cb-workshop-share-confirm-course': '',
          style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: cb3Role('ink'), maxWidth: '54ch' },
          children: `“${item.title}” will be published to the Coursebook store.`
        }),
        jsx('ul', {
          'data-cb-workshop-share-confirm-consequences': '',
          style: { margin: 0, paddingLeft: '1.1rem', display: 'grid', gap: '0.3rem', fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: cb3Role('ink') },
          children: [
            jsx('li', { children: 'A public GitHub pull request will be opened against the Coursebook repository.' }, 'pull-request'),
            jsx('li', { children: 'A fork of the Coursebook repository will be created under your GitHub account.' }, 'fork'),
            jsx('li', { children: 'Anyone can install the course once the repository owner merges that pull request.' }, 'public')
          ]
        }),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem', paddingTop: '0.2rem' },
          children: [
            jsx(CbAction, {
              variant: 'primary',
              'data-cb-workshop-share-confirm-publish': '',
              onClick: onConfirm,
              children: 'Publish course'
            }),
            jsx(CbAction, {
              variant: 'secondary',
              autoFocus: true,
              'data-cb-workshop-share-confirm-cancel': '',
              onClick: onCancel,
              children: 'Cancel'
            })
          ]
        })
      ]
    })
  })
}

/* ── Share to store ────────────────────────────────────────────────────────────────────────
 * The one action that leaves this machine on purpose. It posts one enrollment id to the host,
 * which exports the course there (never here), audits the pack with the importer's own gate, and
 * opens exactly one pull request against the Coursebook repository for the owner to merge. The
 * page never sends a path, never claims the pull request is accepted, and shows the pack id and
 * hashes the host returned so the author can check what they offered.
 */
function WorkshopShare() {
  const [items, setItems] = useState(null)
  const [busy, setBusy] = useState('')
  const [pending, setPending] = useState(null)
  const [outcome, setOutcome] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        const response = await rpc('library.list', {})
        const rows = (response && response.result && response.result.items) || []
        // A pack-backed course belongs to its pack's author: only authored courses can be shared.
        if (live) {
          setItems(
            rows.filter(
              (row) =>
                row.course_status !== 'deleted' && !(row.provenance && row.provenance.pack_id)
            )
          )
        }
      } catch (err) {
        if (live) {
          setItems([])
          setError('Your courses could not be read; nothing was shared.')
        }
      }
    })()
    return () => {
      live = false
    }
  }, [])

  const publish = async (item) => {
    // The request is only reachable after WorkshopShareConfirm's publish control has fired.
    setPending(null)
    setBusy(item.enrollment_id)
    setOutcome(null)
    setError('')
    try {
      const response = await rest('/workshop/share', {
        method: 'POST',
        body: { enrollment_id: item.enrollment_id, confirm: true }
      })
      if (!response || response.ok !== true) {
        setError((response && response.message) || 'The store refused this course; nothing was published.')
      } else {
        setOutcome(response)
      }
    } catch (err) {
      setError('The host could not reach GitHub; nothing was published.')
    } finally {
      setBusy('')
    }
  }

  const heading = jsx('h2', {
    style: { ...workshopStateHeadingStyle, margin: 0 },
    children: 'Share a course with everyone'
  })

  if (items === null) {
    return jsxs('div', { 'data-cb-workshop-share': 'loading', style: { display: 'grid', gap: '0.75rem' }, children: [heading, jsx('p', { children: 'Reading your courses…' })] })
  }

  if (!items.length) {
    return jsxs('div', {
      'data-cb-workshop-share': 'empty',
      style: { display: 'grid', gap: '0.75rem', maxWidth: '46rem' },
      children: [
        heading,
        jsx('p', { children: 'You have no course of your own to share yet. A course you generate appears here once its plan is approved and its lessons are written.' }),
        jsx('p', { style: { color: cb3Role('ink-soft') }, children: 'Packs from the store are shared by their authors, not from this page.' })
      ]
    })
  }

  return jsxs('div', {
    'data-cb-workshop-share': 'ready',
    style: { display: 'grid', gap: '1rem', maxWidth: '52rem' },
    children: [
      heading,
      jsx('p', {
        style: { margin: 0, color: cb3Role('ink-soft') },
        children:
          'Sharing exports this course, checks it against the same rules an imported pack must pass, and opens one pull request on the Coursebook repository. Once that pull request is merged the course is in the store; it reaches other people\'s Workshop with the next plugin update.'
      }),
      outcome
        ? jsxs('div', {
            'data-cb-workshop-share-result': 'ok',
            style: { border: `1px solid ${cb3Role('rule')}`, borderRadius: '0.5rem', padding: '0.75rem', display: 'grid', gap: '0.35rem' },
            children: [
              jsx('strong', {
                children:
                  outcome.status === 'already_present'
                    ? 'The store already has this course'
                    : outcome.status === 'update'
                      ? 'Pull request opened — this replaces the older version'
                      : 'Pull request opened'
              }),
              jsx('div', {
                children:
                  outcome.status === 'already_present'
                    ? `${outcome.pack_id} · these exact bytes are already published`
                    : `${outcome.pack_id} · ${outcome.mode} · ${shareCount(outcome.objectives, 'objective')} · ${shareCount(outcome.world_plates || 0, 'plate')}`
              }),
              jsx('div', { style: { color: cb3Role('ink-soft'), wordBreak: 'break-all' }, children: outcome.content_hash }),
              outcome.pull_request
                ? jsx('a', { href: outcome.pull_request, target: '_blank', rel: 'noreferrer', children: outcome.pull_request })
                : null
            ]
          })
        : null,
      error
        ? jsx('div', {
            'data-cb-workshop-share-result': 'error',
            role: 'status',
            style: { border: `1px solid ${cb3Role('rule')}`, borderRadius: '0.5rem', padding: '0.75rem' },
            children: error
          })
        : null,
      jsx('ul', {
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' },
        children: items.map((item) =>
          jsxs('li', {
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.5rem',
              borderBottom: `1px solid ${cb3Role('rule')}`,
              paddingBottom: '0.5rem'
            },
            children: [
              jsxs('span', { style: { display: 'grid', gap: '0.15rem' }, children: [
                jsx('strong', { children: item.title }),
                jsx('span', { style: { color: cb3Role('ink-soft'), fontSize: cb3Type('meta') }, children: `${item.recipe || 'course'} · ${item.locale || 'unscoped'}` })
              ] }),
              jsx(CbAction, {
                variant: 'secondary',
                disabled: busy === item.enrollment_id,
                onClick: () => setPending(item),
                children: busy === item.enrollment_id ? 'Opening pull request…' : 'Share to store'
              })
            ]
          }, item.enrollment_id)
        )
      }),
      pending
        ? jsx(WorkshopShareConfirm, {
            item: pending,
            onConfirm: () => publish(pending),
            onCancel: () => setPending(null)
          })
        : null
    ]
  })
}
