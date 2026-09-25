import { useCallback, useEffect, useRef, useState } from 'react'

export const limitar = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v))

/** 0 -> 1 entre `a` e `b` segundos. */
export const janela = (t, a, b) => limitar((t - a) / (b - a))

/** Ease-out expo: arranca rapido e pousa devagar, sem quique. */
export const expo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x))

/** Ease-in-out suave, para movimentos de ida e volta. */
export const suave = (x) => x * x * (3 - 2 * x)

export const lerp = (a, b, k) => a + (b - a) * k

/**
 * Relogio da animacao, em segundos.
 *
 * Toca quando a secao fica pelo menos 60% visivel e pausa quando sai. Ao
 * terminar, para no quadro final. Se a pessoa sair e voltar depois do fim,
 * toca de novo do inicio. `reiniciar` e' o "Assistir de novo".
 *
 * O passo de tempo e' limitado a 50 ms: uma aba em segundo plano, ou uma queda
 * de quadros no compartilhamento de tela, nao faz a animacao pular um estado.
 */
export function useLinhaDoTempo(ref, duracao, ativo = true) {
  const [t, setT] = useState(0)
  const [fim, setFim] = useState(false)
  const tRef = useRef(0)
  const visivel = useRef(false)
  const terminou = useRef(false)
  const quadro = useRef(0)
  const anterior = useRef(0)

  const parar = () => {
    cancelAnimationFrame(quadro.current)
    quadro.current = 0
  }

  const tocar = useCallback(() => {
    if (quadro.current || terminou.current) return
    anterior.current = performance.now()
    const passo = (agora) => {
      const dt = Math.min(0.05, (agora - anterior.current) / 1000)
      anterior.current = agora
      tRef.current = Math.min(duracao, tRef.current + dt)
      setT(tRef.current)
      if (tRef.current >= duracao) {
        terminou.current = true
        quadro.current = 0
        setFim(true)
        return
      }
      quadro.current = requestAnimationFrame(passo)
    }
    quadro.current = requestAnimationFrame(passo)
  }, [duracao])

  const reiniciar = useCallback(() => {
    parar()
    terminou.current = false
    tRef.current = 0
    setT(0)
    setFim(false)
    if (visivel.current) tocar()
  }, [tocar])

  useEffect(() => {
    if (!ativo || !ref.current) return undefined
    if (typeof IntersectionObserver === 'undefined') {
      // Sem observer (testes, navegador antigo): mostra o quadro final.
      tRef.current = duracao
      setT(duracao)
      setFim(true)
      return undefined
    }
    const obs = new IntersectionObserver(
      ([e]) => {
        const dentro = e.intersectionRatio >= 0.6
        if (dentro === visivel.current) return
        visivel.current = dentro
        if (dentro) {
          if (terminou.current) reiniciar()
          else tocar()
        } else {
          parar()
        }
      },
      { threshold: [0, 0.6, 1] }
    )
    obs.observe(ref.current)
    return () => {
      obs.disconnect()
      parar()
    }
  }, [ativo, duracao, tocar, reiniciar]) // eslint-disable-line react-hooks/exhaustive-deps

  return { t, fim, reiniciar }
}

/** Largura e altura da janela, atualizadas no resize. */
export function useJanela() {
  const ler = () =>
    typeof window === 'undefined'
      ? { w: 1440, h: 900 }
      : { w: window.innerWidth, h: window.innerHeight }
  const [dim, setDim] = useState(ler)
  useEffect(() => {
    const mudou = () => setDim(ler())
    window.addEventListener('resize', mudou)
    return () => window.removeEventListener('resize', mudou)
  }, [])
  return dim
}
