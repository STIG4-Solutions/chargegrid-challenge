import { useEffect, useState } from 'react'
import { configureSdk, power, useApi } from '@chargegrid/sdk'

const CHAVE = 'chargegrid.site'

/**
 * Seletor de praça, para quem administra mais de uma.
 *
 * Escrever no SDK em vez de propagar por props é o que faz o seletor valer
 * para as telas que já existem: elas continuam chamando `power.plan()` sem
 * saber que existe multi-site, e o `site_id` entra na URL pelo cliente.
 *
 * Some quando há um site só — que é o caso do operador. Ele não escolhe nada:
 * a API ignora o parâmetro para quem não é admin, então mostrar um seletor
 * inerte só prometeria um poder que ele não tem.
 */
export default function SiteSwitcher({ onTrocar }) {
  const sites = useApi(() => power.visibleSites(), [])
  const [escolhido, setEscolhido] = useState(null)

  // Restaura a escolha anterior assim que a lista chega, e só se o site ainda
  // existir: um id salvo apontando para uma praça removida faria toda
  // requisição responder 404 até alguém limpar o armazenamento do navegador.
  useEffect(() => {
    if (!sites.data || sites.data.length === 0) return
    let salvo = null
    try {
      salvo = window.localStorage.getItem(CHAVE)
    } catch {
      salvo = null
    }
    const valido = sites.data.some((s) => s.site_id === salvo) ? salvo : null
    setEscolhido(valido)
    configureSdk({ siteId: valido })
  }, [sites.data])

  if (!sites.data || sites.data.length < 2) return null

  function trocar(id) {
    const valor = id || null
    setEscolhido(valor)
    configureSdk({ siteId: valor })
    try {
      if (valor) window.localStorage.setItem(CHAVE, valor)
      else window.localStorage.removeItem(CHAVE)
    } catch {
      // Navegador sem armazenamento: a escolha vale para esta sessão e pronto.
    }
    onTrocar?.(valor)
  }

  return (
    <label style={{ fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span className="muted">Praça</span>
      <select value={escolhido || ''} onChange={(e) => trocar(e.target.value)}>
        <option value="">Padrão da conta</option>
        {sites.data.map((s) => (
          <option key={s.site_id} value={s.site_id}>
            {s.nome}
            {s.cidade ? ` — ${s.cidade}` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
