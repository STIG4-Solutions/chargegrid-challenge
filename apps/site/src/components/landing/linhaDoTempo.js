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
 * Relogio da animacao, em segundos. `ref` e' o PALCO (o elemento fixo).
 *
 * Comeca quando o palco fica fixo na tela (inteiro visivel). Pausa se menos de
 * 60% dele estiver na tela, e retoma ao voltar. Ao terminar, para no quadro
 * final; se a pessoa sair e voltar depois do fim, toca de novo do inicio.
 * `reiniciar` e' o "Assistir de novo".
 *
 * O passo de tempo e' limitado a 50 ms: uma aba em segundo plano, ou uma queda
 * de quadros no compartilhamento de tela, nao faz a animacao pular um estado.
 */
export function useLinhaDoTempo(ref, duracao, ativo = true) {
  const [t, setT] = useState(0)
  const [fim, setFim] = useState(false)
  const tRef = useRef(0)
  const visivel = useRef(false)
  const comecou = useRef(false)
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
    let saiuDepoisDoFim = false
    const obs = new IntersectionObserver(
      ([e]) => {
        const r = e.intersectionRatio
        const fixo = r >= 0.98
        visivel.current = r >= 0.6
        if (!visivel.current) {
          parar()
          if (terminou.current) saiuDepoisDoFim = true
          return
        }
        if (fixo && (!comecou.current || saiuDepoisDoFim)) {
          comecou.current = true
          if (saiuDepoisDoFim) {
            saiuDepoisDoFim = false
            reiniciar()
          } else tocar()
          return
        }
        // Voltou depois de uma pausa no meio: retoma de onde parou.
        if (comecou.current && !terminou.current) tocar()
      },
      { threshold: [0, 0.6, 0.98, 1] }
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

/**
 * Encaixe leve na chegada: quando uma rolagem PARA BAIXO termina com o inicio
 * do bloco logo abaixo (ate' 30% da tela), a pagina desliza ate' ele.
 *
 * Por que nao `scroll-snap-type: y proximity` no CSS: o Chromium encaixa sempre
 * que a rolagem para a ate' 1/3 da tela do ponto - inclusive DEPOIS de passar
 * por ele. Com roda de mouse em degraus, cada clique de 100 px era devolvido ao
 * inicio do bloco, e a pagina ficava presa. Aqui nunca se puxa para tras: passou
 * do inicio, nao ha' encaixe.
 *
 * Nao intercepta wheel, touch nem teclado: so' le a posicao quando a rolagem
 * termina (`scrollend`, ou 150 ms sem scroll onde o evento nao existe).
 */
export function useEncaixeNaChegada(ref, ativo = true) {
  useEffect(() => {
    if (!ativo || typeof window === 'undefined') return undefined
    let ultimoY = window.scrollY
    let desceu = false
    let espera = 0
    let encaixando = false
    const temScrollEnd = 'onscrollend' in window

    const terminou = () => {
      const el = ref.current?.parentElement
      if (!el || encaixando || !desceu) return
      const topo = el.getBoundingClientRect().top
      if (topo > 1 && topo <= window.innerHeight * 0.3) {
        encaixando = true
        window.scrollTo({ top: window.scrollY + topo, behavior: 'smooth' })
        setTimeout(() => (encaixando = false), 700)
      }
    }
    const rolou = () => {
      const y = window.scrollY
      if (y !== ultimoY) desceu = y > ultimoY
      ultimoY = y
      if (!temScrollEnd) {
        clearTimeout(espera)
        espera = setTimeout(terminou, 150)
      }
    }
    window.addEventListener('scroll', rolou, { passive: true })
    if (temScrollEnd) window.addEventListener('scrollend', terminou)
    return () => {
      window.removeEventListener('scroll', rolou)
      window.removeEventListener('scrollend', terminou)
      clearTimeout(espera)
    }
  }, [ref, ativo])
}
