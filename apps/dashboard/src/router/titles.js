// Mapa de títulos por rota (usado no header e no document.title)
export const titles = {
  '/station_monitor': 'Lista de usinas',
  '/device': 'Dispositivos',
  '/alarm': 'Alarmes',
  '/report': 'Relatórios',
  '/statistics': 'Estatísticas',
  '/om': 'Operação & Manutenção',
  '/ev': 'Recarga EV',
  '/ev/power': 'Gerenciamento de Potência',
  '/ev/sessions': 'Ciclo da Sessão',
  '/ev/tariff': 'Tarifação & Pagamento',
  '/ev/campaigns': 'Campanhas',
  '/ev/contract': 'Plano & Contrato',
  '/ev/audit': 'Auditoria'
}

export function titleFor(pathname) {
  if (titles[pathname]) return titles[pathname]
  // pega o prefixo mais longo que casar
  const key = Object.keys(titles)
    .filter((k) => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0]
  return key ? titles[key] : 'SEMS+'
}
