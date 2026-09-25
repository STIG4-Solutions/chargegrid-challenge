import { useEffect, useRef } from 'react'
import { faixa, useReducedMotion, useScrollProgress } from './hooks.js'
import { BotaoApp, BotaoPainel, LogoGoodWe } from './Marcas.jsx'

// Quadros inteiros (1280 x 720) dos primeiros 7 s do video, a 12 por segundo.
// A rolagem do hero e' curta; o video nao precisa aparecer inteiro.
const QUADROS = 84
const url = (i) => `/landing/hero/f${String(i + 1).padStart(3, '0')}.webp`

// Foco horizontal do "cover": 0 = borda esquerda do quadro, 1 = direita. Em
// 0,28 o carregador (x ~ 330-500 no original) fica logo depois do degrade da
// esquerda, e a frente do carro ao lado dele.
const FOCO_X = 0.28
// Quanto o quadro exibido anda em direcao ao alvo a cada animation frame.
const SUAVIZACAO = 0.12

/** Desenha `img` cobrindo o canvas inteiro, como object-fit: cover. */
function desenharCobrindo(ctx, img, w, h) {
  const escala = Math.max(w / img.naturalWidth, h / img.naturalHeight)
  const sw = w / escala
  const sh = h / escala
  const sx = (img.naturalWidth - sw) * FOCO_X
  const sy = (img.naturalHeight - sh) / 2
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, w, h)
}

/**
 * Sequencia de quadros no canvas. O alvo vem da rolagem; o quadro exibido o
 * persegue com interpolacao a cada requestAnimationFrame, nos dois sentidos,
 * e o laco para sozinho quando alcanca.
 */
function useSequencia(canvasRef, alvo, ativo) {
  const imagens = useRef([])
  const atual = useRef(0)
  const alvoRef = useRef(0)
  const quadro = useRef(0)
  const ultimo = useRef(-1)

  const desenhar = (forcar = false) => {
    const canvas = canvasRef.current
    let ctx = null
    try {
      ctx = canvas?.getContext('2d')
    } catch {
      ctx = null
    }
    if (!ctx) return
    let i = Math.round(atual.current)
    while (i >= 0 && !imagens.current[i]?.complete) i--
    if (i < 0 || (i === ultimo.current && !forcar)) return
    desenharCobrindo(ctx, imagens.current[i], canvas.width, canvas.height)
    ultimo.current = i
  }

  const passo = () => {
    const falta = alvoRef.current - atual.current
    atual.current = Math.abs(falta) < 0.05 ? alvoRef.current : atual.current + falta * SUAVIZACAO
    desenhar()
    quadro.current = atual.current === alvoRef.current ? 0 : requestAnimationFrame(passo)
  }

  // O canvas tem o tamanho da caixa (x densidade da tela, ate' 2): o cover e'
  // feito no desenho, sem esticar bitmap.
  useEffect(() => {
    if (!ativo) return undefined
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const ajustar = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1)
      canvas.width = Math.round(canvas.clientWidth * dpr)
      canvas.height = Math.round(canvas.clientHeight * dpr)
      desenhar(true)
    }
    ajustar()
    const obs = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(ajustar) : null
    obs?.observe(canvas)
    return () => obs?.disconnect()
  }, [ativo]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!ativo) return undefined
    const carregar = (i) => {
      const img = new Image()
      img.decoding = 'async'
      img.onload = () => {
        if (Math.abs(i - atual.current) < 2) desenhar(true)
      }
      img.src = url(i)
      imagens.current[i] = img
    }
    carregar(0)
    const ocioso = window.requestIdleCallback ?? ((fn) => setTimeout(fn, 60))
    const id = ocioso(() => {
      for (let i = 1; i < QUADROS; i++) carregar(i)
    })
    return () => {
      window.cancelIdleCallback?.(id)
      cancelAnimationFrame(quadro.current)
      // Zerado junto: com o id antigo aqui, o laco nunca mais reiniciaria (o
      // StrictMode desmonta e monta os efeitos uma vez em desenvolvimento).
      quadro.current = 0
    }
  }, [ativo]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!ativo) return
    alvoRef.current = alvo * (QUADROS - 1)
    if (!quadro.current) quadro.current = requestAnimationFrame(passo)
  }, [alvo, ativo]) // eslint-disable-line react-hooks/exhaustive-deps
}

export default function Hero() {
  const secao = useRef(null)
  const canvas = useRef(null)
  const reduzido = useReducedMotion()
  const p = useScrollProgress(secao, !reduzido)
  useSequencia(canvas, reduzido ? 1 : p, !reduzido)
  const card = reduzido ? 1 : faixa(p, 0.55, 0.9)

  return (
    <section id="inicio" ref={secao} className={`lp-hero ${reduzido ? 'lp-estatico' : ''}`}>
      <div className="lp-hero-palco">
        <div className="lp-hero-midia">
          {reduzido ? (
            <img
              className="lp-hero-imagem"
              src={url(QUADROS - 1)}
              alt="Carregador GoodWe com um carro plugado, à noite"
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
                role="img"
                aria-label="A câmera se aproxima de um carregador GoodWe com um carro plugado, à noite"
              />
            </>
          )}
          <span className="lp-hero-degrade" aria-hidden="true" />
          <LogoGoodWe className="lp-hero-selo" />
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

        <div className="lp-hero-texto">
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
      </div>
    </section>
  )
}
