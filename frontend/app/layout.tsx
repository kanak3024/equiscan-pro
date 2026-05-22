import type { Metadata } from 'next'
import './globals.css'
import Navbar from '../components/Navbar'

export const metadata: Metadata = {
  title: 'EquiScan Pro',
  description: 'Indian Stock Screener',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-[#0a0c10] text-white min-h-screen">
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  )
}