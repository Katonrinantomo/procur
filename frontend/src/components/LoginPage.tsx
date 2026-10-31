/**
 * LoginPage — simple username/password form that POSTs to the backend
 * auth endpoint and stores the JWT, role, and username in localStorage.
 */
import { useState } from 'react'
import { fetchWithAuth } from '../lib/api'

interface LoginPageProps {
  onLogin: (role: string) => void
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(() => {
    // Show session-expired message if redirected here by fetchWithAuth
    const msg = sessionStorage.getItem('auth_message')
    if (msg) {
      sessionStorage.removeItem('auth_message')
      return msg
    }
    return null
  })
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await fetchWithAuth('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      if (res.status === 429) {
        setError('Terlalu banyak percobaan. Coba lagi dalam satu menit.')
        return
      }
      if (!res.ok) {
        setError('Username atau password salah')
        return
      }

      const data = await res.json() as { access_token: string; role: string; username: string }
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('role', data.role)
      localStorage.setItem('username', data.username)
      onLogin(data.role)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#F7F7F5',
    }}>
      <div style={{
        background: '#FFFFFF',
        border: '1px solid #E6E6E2',
        borderRadius: 12,
        padding: 32,
        width: '100%',
        maxWidth: 380,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Procur.AI</h1>
          <p style={{ margin: 0, fontSize: 14, color: '#6B6B66' }}>Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: '#4A4A46' }}>
            Username
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={{
                height: 40,
                padding: '0 12px',
                border: '1px solid #D9D9D5',
                borderRadius: 8,
                font: 'inherit',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: '#4A4A46' }}>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{
                height: 40,
                padding: '0 12px',
                border: '1px solid #D9D9D5',
                borderRadius: 8,
                font: 'inherit',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          </label>

          {error && (
            <span style={{ fontSize: 13, color: '#9A3412' }}>{error}</span>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              height: 44,
              border: 0,
              borderRadius: 10,
              background: '#1A1A1A',
              color: '#FFFFFF',
              font: 'inherit',
              fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p style={{ margin: 0, fontSize: 12, color: '#9E9E99', textAlign: 'center' }}>
          Demo users: purchasing / owner / finance
        </p>
      </div>
    </div>
  )
}
