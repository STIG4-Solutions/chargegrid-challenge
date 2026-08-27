/**
 * Assinatura do WebSocket do site. `WebSocket` existe no navegador e no React
 * Native, então este hook serve os dois.
 */
import { useEffect, useRef, useState } from 'react'
import { socketUrl } from './config'
import { accessToken } from './tokens'
import type { Orcamento } from './types'

export type StatusDoStream = 'idle' | 'connecting' | 'reconnecting' | 'online' | 'offline' | 'error'

export interface TelemetriaDoSite {
  recorded_at: string
  budget: Orcamento
  charge_points: Array<{
    id: string
    code: string
    status: string
    current_kw: number
    limit_kw: number
    faults: string[]
  }>
}

// Sem tráfego, um ping periódico impede proxies de matar a conexão.
const INTERVALO_PING_MS = 25_000

export function useSiteStream({ enabled = true } = {}) {
  const [status, setStatus] = useState<StatusDoStream>('connecting')
  const [telemetry, setTelemetry] = useState<TelemetriaDoSite | null>(null)
  const [powerPlan, setPowerPlan] = useState<Record<string, unknown> | null>(null)

  const socketRef = useRef<WebSocket | null>(null)
  const tentativaRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (!enabled) {
      setStatus('idle')
      return undefined
    }
    let fechadoPorNos = false

    function conectar() {
      setStatus(tentativaRef.current === 0 ? 'connecting' : 'reconnecting')
      const socket = new WebSocket(socketUrl('/ws/site', accessToken()))
      socketRef.current = socket

      socket.onopen = () => {
        tentativaRef.current = 0
        setStatus('online')
      }

      socket.onmessage = (evento: MessageEvent) => {
        let mensagem: { type?: string; data?: unknown }
        try {
          mensagem = JSON.parse(String(evento.data))
        } catch {
          return
        }
        // "ping" é keep-alive do servidor; não carrega dado.
        if (mensagem.type === 'telemetry') setTelemetry(mensagem.data as TelemetriaDoSite)
        else if (mensagem.type === 'power_plan') {
          setPowerPlan(mensagem.data as Record<string, unknown>)
        }
      }

      socket.onerror = () => setStatus('error')

      socket.onclose = () => {
        if (fechadoPorNos) return
        setStatus('offline')
        // 1s, 2s, 4s… até 30s — sem martelar o servidor que acabou de cair.
        const espera = Math.min(30_000, 1000 * 2 ** tentativaRef.current)
        tentativaRef.current += 1
        timerRef.current = setTimeout(conectar, espera)
      }
    }

    conectar()

    return () => {
      fechadoPorNos = true
      clearTimeout(timerRef.current)
      socketRef.current?.close()
    }
  }, [enabled])

  return { status, telemetry, powerPlan }
}
