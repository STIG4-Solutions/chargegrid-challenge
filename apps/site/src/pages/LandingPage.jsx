import { useEffect } from 'react'
import Cabecalho from '../components/landing/Cabecalho.jsx'
import ComoFunciona from '../components/landing/ComoFunciona.jsx'
import Hero from '../components/landing/Hero.jsx'
import Problema from '../components/landing/Problema.jsx'
import Tecnologia from '../components/landing/Tecnologia.jsx'
import '../styles/landing.css'

export default function LandingPage() {
  useEffect(() => {
    const titulo = document.title
    const tema = document.querySelector('meta[name="theme-color"]')
    const temaAnterior = tema?.getAttribute('content')
    document.title = 'ChargeGrid · Recarga que dá lucro sem estourar a energia da sua loja'
    tema?.setAttribute('content', '#0d0d0f')
    return () => {
      document.title = titulo
      if (tema && temaAnterior) tema.setAttribute('content', temaAnterior)
    }
  }, [])

  return (
    <div className="lp">
      <Cabecalho />
      <main>
        <Hero />
        <Problema />
        <ComoFunciona />
        <Tecnologia />
      </main>
    </div>
  )
}
