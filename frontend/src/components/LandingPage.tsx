/**
 * LandingPage — shown before login.
 * Clean, minimal design using the project's existing style tokens.
 * No gradients, no shadows.
 */
interface LandingPageProps {
  onLoginClick: () => void
}

const FEATURES = [
  {
    title: '1. Ekstraksi AI',
    desc: 'Ubah pesan WhatsApp berantakan menjadi data terstruktur dengan Langflow.',
  },
  {
    title: '2. Web Price Check',
    desc: 'Cari harga pasar secara real-time dari Tokopedia & Shopee sebagai referensi.',
  },
  {
    title: '3. Audit Trail',
    desc: 'Jejak rekam digital siapa yang menyetujui pengadaan, kapan, dan alasannya.',
  },
]

export default function LandingPage({ onLoginClick }: LandingPageProps) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#FFFFFF', color: '#1A1A1A' }}>

      {/* Header */}
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 28px',
        background: '#FFFFFF',
        borderBottom: '1px solid #E6E6E2',
      }}>
        <span style={{ fontSize: 20, fontWeight: 700 }}>Procur.AI</span>
        <button
          type="button"
          onClick={onLoginClick}
          style={{
            height: 40,
            padding: '0 20px',
            border: 0,
            borderRadius: 8,
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

      {/* Hero */}
      <section style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '112px 28px',
        gap: 24,
      }}>
        <h1 style={{
          margin: 0,
          fontSize: 48,
          fontWeight: 700,
          lineHeight: 1.15,
          maxWidth: 800,
        }}>
          Cegah Kebocoran Anggaran dengan AI Maker-Checker.
        </h1>
        <p style={{
          margin: 0,
          fontSize: 18,
          lineHeight: 1.55,
          color: '#4A4A46',
          maxWidth: 600,
        }}>
          Procur.AI membantu perusahaan menengah mengecek harga, memvalidasi supplier, dan mengaudit setiap pengadaan secara otomatis sebelum uang keluar.
        </p>
        <button
          type="button"
          onClick={onLoginClick}
          style={{
            padding: '14px 28px',
            border: 0,
            borderRadius: 8,
            background: '#1A1A1A',
            color: '#FFFFFF',
            font: 'inherit',
            fontSize: 16,
            fontWeight: 500,
            cursor: 'pointer',
            marginTop: 8,
          }}
        >
          Mulai Sekarang
        </button>
      </section>

      {/* Features */}
      <section style={{
        background: '#F7F7F5',
        padding: '60px 20px',
        borderTop: '1px solid #E6E6E2',
        borderBottom: '1px solid #E6E6E2',
      }}>
        <div style={{
          maxWidth: 1080,
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 20,
        }}>
          {FEATURES.map((f) => (
            <div
              key={f.title}
              style={{
                background: '#FFFFFF',
                border: '1px solid #E6E6E2',
                borderRadius: 12,
                padding: 24,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{f.title}</h3>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: '#4A4A46' }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        padding: '24px 28px',
        textAlign: 'center',
        fontSize: 13,
        color: '#6B6B66',
      }}>
        © 2026 Procur.AI. Dibangun untuk IBM SkillsBuild Hackathon.
      </footer>
    </div>
  )
}
