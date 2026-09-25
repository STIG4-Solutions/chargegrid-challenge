import { useEffect, useRef, useState } from 'react'

const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v))

/** 0 -> 1 conforme `inicio`..`fim`; fora do intervalo, preso nas pontas. */
export function faixa(valor, inicio, fim) {
  return clamp((valor - inicio) / (fim - inicio))
}

/**
 * `true` quando o sistema pede menos movimento. Sem `matchMedia` (testes,
 * navegadores antigos), responde `false` e a pagina segue estatica onde precisa.
 */
export function useReducedMotion() {
  const [reduzido, setReduzido] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })
  useEffect(() => {
    if (!window.matchMedia) return undefined
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const mudou = () => setReduzido(mq.matches)
    mq.addEventListener?.('change', mudou)
    return () => mq.removeEventListener?.('change', mudou)
  }, [])
  return reduzido
}

/**
 * Progresso de rolagem de uma secao alta com filho `sticky`: 0 quando o topo
 * dela encosta no topo da tela, 1 quando o fim dela encosta no fim da tela.
 * Uma leitura por quadro (requestAnimationFrame), nunca por evento de scroll.
 */
export function useScrollProgress(ref, ativo = true) {
  const [progresso, setProgresso] = useState(0)
  useEffect(() => {
    if (!ativo) return undefined
    let quadro = 0
    const medir = () => {
      quadro = 0
      const el = ref.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const percurso = r.height - window.innerHeight
      setProgresso(percurso > 0 ? clamp(-r.top / percurso) : 0)
    }
    const agendar = () => {
      if (!quadro) quadro = requestAnimationFrame(medir)
    }
    medir()
    window.addEventListener('scroll', agendar, { passive: true })
    window.addEventListener('resize', agendar)
    return () => {
      cancelAnimationFrame(quadro)
      window.removeEventListener('scroll', agendar)
      window.removeEventListener('resize', agendar)
    }
  }, [ref, ativo])
  return progresso
}

/** `true` uma unica vez, quando o elemento entra na tela. Sem observer, ja' nasce `true`. */
export function useEntrouNaTela(opcoes = { threshold: 0.35 }) {
  const ref = useRef(null)
  const [entrou, setEntrou] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (entrou || !ref.current || typeof IntersectionObserver === 'undefined') return undefined
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        setEntrou(true)
        obs.disconnect()
      }
    }, opcoes)
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [entrou]) // eslint-disable-line react-hooks/exhaustive-deps
  return [ref, entrou]
}
