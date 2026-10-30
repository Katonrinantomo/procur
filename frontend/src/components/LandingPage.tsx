/**
 * LandingPage — shown before login.
 * Clean, minimal design using the project's existing style tokens.
 */
interface LandingPageProps {
  onLoginClick: () => void
}

export default function LandingPage({ onLoginClick }: LandingPageProps) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#FFFFFF', color: '#1A1A1A' }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 28px',
        borderBottom: '1px solid #EDEDEA',
      }}>
        <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>Procur.AI</span>
        <button
          type="button"
          onClick={onLoginClick}
          style={{
            height: 40,
            padding: '0 18px',
            border: 0,
            borderRadius: 10,
            background: '#1A1A1A',
            color: '#FFFFFF',
            font: 'inherit',
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          Masuk
        </button>
      </header>

      {/* ── Hero ── */}
      <section style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '80px 28px 64px',
        gap: 20,
      }}>
        <h1 style={{
          margin: 0,
          fontSize: 'clamp(28px, 5vw, 44px)',
          fontWeight: 600,
          lineHeight: 1.2,
          maxWidth: 720,
        }}>
          Cegah Kebocoran Anggaran dengan AI Maker-Checker.
        </h1>
        <p style={{
          margin: 0,
          fontSize: 17,
          color: '#4A4A46',
          maxWidth: 560,
          lineHeight: 1.55,
        }}>
          Procur.AI membantu perusahaan menengah mengecek harga, memvalidasi supplier, dan mengaudit setiap pengadaan secara otomatis sebelum uang keluar.
        </p>
        <button
          type="button"
          onClick={onLoginClick}
          style={{
            height: 48,
            padding: '0 28px',
            border: 0,
            borderRadius: 12,
            background: '#1A1A1A',
            color: '#FFFFFF',
            font: 'inherit',
            fontSize: 15,
            fontWeight: 500,
            cursor: 'pointer',
            marginTop: 8,
          }}
        >
          Mulai Sekarang
        </button>
      </section>

      {/* ── Features ── */}
      <section style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: 16,
        padding: '0 28px 64px',
        maxWidth: 1080,
        margin: '0 auto',
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {[
          {
            num: '1',
            title: 'Ekstraksi AI',
            desc: 'Organize pesan WhatsApp berantakan menjadi data terstruktur.',
          },
          {
            num: '2',
            title: 'Web Price Check',
            desc: 'Cari harga pasar secara real-time dari Tokopedia & Shopee.',
          },
          {
            num: '3',
            title: 'Audit Trail (Maker-Checker)',
            desc: 'Jejak rekam digital siapa yang menyetujui pengadaan dan alasannya.',
          },
        ].map((f) => (
          <div
            key={f.num}
            style={{
              flex: '1 1 280px',
              minWidth: 260,
              border: '1px solid #E6E6E2',
              borderRadius: 12,
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <span style={{
              fontSize: 13,
              fontWeight: 600,
              color: '#9A3412',
              background: '#FFF4EC',
              width: 28,
              height: 28,
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {f.num}
            </span>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{f.title}</h3>
            <p style={{ margin: 0, fontSize: 14, color: '#4A4A46', lineHeight: 1.5 }}>{f.desc}</p>
          </div>
        ))}
      </section>

      {/* ── Footer ── */}
      <footer style={{
        borderTop: '1px solid #EDEDEA',
        padding: '20px 28px',
        textAlign: 'center',
        fontSize: 13,
        color: '#9E9E99',
      }}>
        © 2026 Procur.AI
      </footer>
    </div>
  )
}