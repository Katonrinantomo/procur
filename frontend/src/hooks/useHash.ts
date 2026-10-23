import { useEffect, useState } from 'react'

/**
 * Returns the current window.location.hash (including the '#' prefix,
 * e.g. "#today") and re-renders whenever it changes.
 * Defaults to "#today" when the hash is empty.
 */
export function useHash(): string {
  const [hash, setHash] = useState<string>(() => {
    const h = window.location.hash
    return h || '#today'
  })

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = '#today'
    }

    function onHashChange() {
      setHash(window.location.hash || '#today')
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return hash
}
