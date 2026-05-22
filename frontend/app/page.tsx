import Link from 'next/link'

export default function Home() {
  return (
    <main style={{ padding: '40px', fontFamily: 'sans-serif' }}>
      <h1>EquiScan Pro</h1>
      <p>Indian Stock Screener — Production Build</p>
      <br />
      <Link href="/screener">Go to Screener →</Link>
    </main>
  )
}