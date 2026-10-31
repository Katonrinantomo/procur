/**
 * fetchWithAuth — wraps the global fetch() so every request automatically
 * carries the JWT from localStorage.
 *
 * On a 401 response the token is removed and the page reloads (forces a
 * re-login) with a message "Sesi berakhir, silakan masuk lagi".
 */
export function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('token')
  const headers = new Headers(options.headers ?? {})
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return fetch(url, { ...options, headers }).then((res) => {
    if (res.status === 401 && url !== '/api/auth/login') {
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('username')
      sessionStorage.setItem('auth_message', 'Sesi berakhir, silakan masuk lagi')
      window.location.reload()
    }
    return res
  })
}