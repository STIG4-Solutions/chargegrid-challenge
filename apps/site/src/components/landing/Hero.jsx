import { useEffect, useRef } from 'react'
import { faixa, useReducedMotion, useScrollProgress } from './hooks.js'
import { BotaoApp, BotaoPainel, CompativelGoodWe } from './Marcas.jsx'

// 120 quadros de 720 x 720, recortados do video em x = 160 (o carregador fica
// inteiro e o canto inferior direito do quadro original, fora).
const QUADROS = 120
const url = (i) => `/landing/hero/f${String(i + 1).padStart(3, '0')}.webp`

/**
 * Desenha no canvas o quadro que corresponde a rolagem. Carrega o primeiro
 * antes dos outros para o canvas nunca nascer vazio; enquanto um quadro nao
 * chegou, repete o mais proximo que ja' chegou.
 */
function useSequencia(canvasRef, progresso, ativo) {
  const imagens = useRef([])
  const desenhado = useRef(-1)
  const alvo = useRef(0)

  const desenhar = (indice) => {
    const canvas = canvasRef.current
    let ctx = null
    try {
      ctx = canvas?.getContext('2d')
    } catch {
      ctx = null
    }
    if (!ctx) return
    let i = indice
    while (i >= 0 && !imagens.current[i]?.complete) i--
    if (i < 0 || i === desenhado.current) return
    ctx.drawImage(imagens.current[i], 0, 0, canvas.width, canvas.height)
    desenhado.current = i
  }

  useEffect(() => {
    if (!ativo) return undefined
    const carregar = (i) => {
      const img = new Image()
      img.decoding = 'async'
      img.onload = () => {
        if (Math.abs(i - alvo.current) < 3) desenhar(alvo.current)
      }
      img.src = url(i)
      imagens.current[i] = img
    }
    carregar(0)
    // O resto em segundo plano, em ordem: a rolagem anda para frente.
    const ocioso = window.requestIdleCallback ?? ((fn) => setTimeout(fn, 60))
    const id = ocioso(() => {
      for (let i = 1; i < QUADROS; i++) carregar(i)
    })
    return () => window.cancelIdleCallback?.(id)
  }, [ativo]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!ativo) return
    alvo.current = Math.round(progresso * (QUADROS - 1))
    desenhar(alvo.current)
  }, [progresso, ativo]) // eslint-disable-line react-hooks/exhaustive-deps
}

export default function Hero() {
  const secao = useRef(null)
  const canvas = useRef(null)
  const reduzido = useReducedMotion()
  const p = useScrollProgress(secao, !reduzido)
  // O video termina em 85% da rolagem; o resto e' do card, parado no carregador.
  const video = reduzido ? 1 : faixa(p, 0, 0.85)
  useSequencia(canvas, video, !reduzido)

  const texto = reduzido ? 1 : 1 - faixa(p, 0.05, 0.33)
  // Com o texto saindo, o quadro vai para o centro do palco: a camera chega ao
  // carregador no meio da tela, e nao encostada num canto vazio.
  const desloca = reduzido ? 0 : faixa(p, 0.08, 0.5)
  const card = reduzido ? 1 : faixa(p, 0.8, 0.95)

  return (
    <section id="inicio" ref={secao} className={`lp-hero ${reduzido ? 'lp-estatico' : ''}`}>
      <div className="lp-hero-palco">
        <div
          className="lp-hero-texto"
          style={{ opacity: texto, transform: `translate3d(0, ${(1 - texto) * -24}px, 0)` }}
        >
          <h1>Recarga que dá lucro sem estourar a energia da sua loja.</h1>
          <p className="lp-lead">
            O ChargeGrid decide sozinho quanta potência cada carro recebe e quanto a recarga custa,
            conforme a energia disponível no seu estabelecimento.
          </p>
          <div className="lp-botoes">
            <BotaoPainel />
            <BotaoApp />
          </div>
          <p className="lp-rolagem" aria-hidden="true">
            <span className="lp-rolagem-linha" />
            Role para ver
          </p>
        </div>

        <div className="lp-hero-midia" style={{ '--lp-desloca': desloca }}>
          <div className="lp-hero-quadro">
            {reduzido ? (
              <img
                className="lp-hero-imagem"
                src="/landing/hero/f120.webp"
                alt="Carregador GoodWe com um carro plugado, à noite"
                width="720"
                height="720"
              />
            ) : (
              <>
                <img
                  className="lp-hero-imagem lp-hero-poster"
                  src="/landing/hero-inicio.jpg"
                  alt=""
                />
                <canvas
                  ref={canvas}
                  className="lp-hero-canvas"
                  width="720"
                  height="720"
                  role="img"
                  aria-label="A câmera se aproxima de um carregador GoodWe com um carro plugado, à noite"
                />
              </>
            )}
            <span className="lp-hero-borda" aria-hidden="true" />
          </div>
          <CompativelGoodWe className="lp-hero-selo" />

          <div
            className="lp-hero-card"
            style={{ opacity: card, transform: `translate3d(0, ${(1 - card) * 16}px, 0)` }}
            aria-hidden={card < 0.5}
          >
            <span className="lp-bandeira-linha">
              <span className="lp-bolinha lp-bolinha-verde" aria-hidden="true" />
              Bandeira verde
            </span>
            <strong>R$ 1,80/kWh se iniciar agora</strong>
          </div>
        </div>
      </div>
    </section>
  )
}
