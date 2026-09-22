import { useEffect } from 'react'
import '../styles/download.css'

const installationSteps = [
  {
    title: 'Baixe o arquivo',
    description: 'Toque no botão de download e aguarde o arquivo APK terminar de baixar.'
  },
  {
    title: 'Autorize o navegador',
    description:
      'Abra o arquivo. Se o Android solicitar, permita a instalação de apps por este navegador.'
  },
  {
    title: 'Confirme a instalação',
    description: 'Volte ao arquivo baixado, toque em Instalar e abra o ChargeGrid.'
  }
]

function ChargeGridMark() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path d="M22.8 2.5 8.6 22.2h9.2l-1.1 15.3 14.7-21.2h-9.6l1-13.8Z" />
    </svg>
  )
}

function AndroidIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7.2 7.6-1.7-3a.75.75 0 1 1 1.3-.75l1.8 3.1a10.2 10.2 0 0 1 6.8 0l1.8-3.1a.75.75 0 1 1 1.3.75l-1.7 3A8 8 0 0 1 21 14H3a8 8 0 0 1 4.2-6.4ZM8 11.2a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" />
      <path d="M3 15.5h18V18a2 2 0 0 1-2 2h-1v1.25a.75.75 0 0 1-1.5 0V20h-9v1.25a.75.75 0 0 1-1.5 0V20H5a2 2 0 0 1-2-2v-2.5Z" />
    </svg>
  )
}

function DownloadArrow() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v12m0 0 5-5m-5 5-5-5M5 21h14" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 5.5 5.7v5.7c0 4.3 2.6 7.8 6.5 9.6 3.9-1.8 6.5-5.3 6.5-9.6V5.7L12 3Z" />
      <path d="m9.3 12 1.8 1.8 3.8-4" />
    </svg>
  )
}

export default function DownloadPage() {
  useEffect(() => {
    const previousTitle = document.title
    const themeColor = document.querySelector('meta[name="theme-color"]')
    const previousThemeColor = themeColor?.getAttribute('content')

    document.title = 'Baixar ChargeGrid para Android'
    themeColor?.setAttribute('content', '#0b0c0f')

    return () => {
      document.title = previousTitle
      if (previousThemeColor) themeColor?.setAttribute('content', previousThemeColor)
    }
  }, [])

  return (
    <main className="download-page">
      <div className="download-page__grid" aria-hidden="true" />

      <header className="download-header">
        <a className="download-brand" href="/" aria-label="ChargeGrid — página inicial">
          <span className="download-brand__mark">
            <ChargeGridMark />
          </span>
          <span>ChargeGrid</span>
        </a>

        <span className="download-header__platform">Android / APK</span>
      </header>

      <section className="download-hero" aria-labelledby="download-title">
        <div className="download-hero__copy">
          <p className="download-eyebrow">
            <span aria-hidden="true" /> Aplicativo Android
          </p>

          <h1 id="download-title">
            Sua recarga
            <span>continua no bolso</span>
          </h1>

          <p className="download-hero__intro">
            Encontre estações, acompanhe cada sessão e mantenha seus veículos, pagamentos e recargas
            em um só lugar.
          </p>

          <div className="download-actions">
            <a className="download-button" href="/download/android">
              <span className="download-button__platform">
                <AndroidIcon />
              </span>
              <span>
                <small>Download direto</small>
                Baixar APK para Android
              </span>
              <DownloadArrow />
            </a>

            <a className="download-text-link" href="#como-instalar">
              Ver como instalar
              <span aria-hidden="true">↓</span>
            </a>
          </div>

          <p className="download-safety">
            <ShieldIcon />
            Use somente o arquivo obtido nesta página oficial.
          </p>
        </div>

        <div className="app-pass" aria-label="Aplicativo ChargeGrid para Android">
          <div className="app-pass__topline">
            <span>CG / MOBILE</span>
            <span className="app-pass__status">
              <i aria-hidden="true" /> Distribuição direta
            </span>
          </div>

          <div className="app-pass__body">
            <div className="app-pass__icon-wrap">
              <span className="app-pass__orbit" aria-hidden="true" />
              <img src="/chargegrid-app-icon.png" alt="Ícone do aplicativo ChargeGrid" />
            </div>

            <div className="app-pass__identity">
              <span>ChargeGrid</span>
              <strong>Energia em movimento.</strong>
            </div>
          </div>

          <div className="app-pass__route" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>

          <dl className="app-pass__details">
            <div>
              <dt>Formato</dt>
              <dd>APK</dd>
            </div>
            <div>
              <dt>Plataforma</dt>
              <dd>Android</dd>
            </div>
            <div>
              <dt>Origem</dt>
              <dd>ChargeGrid</dd>
            </div>
          </dl>

          <div className="app-pass__footer">
            <span>STIG4 / 2026</span>
            <span aria-hidden="true">••••••••••••••••</span>
          </div>
        </div>
      </section>

      <section className="installation" id="como-instalar" aria-labelledby="installation-title">
        <div className="installation__heading">
          <p className="download-eyebrow">
            <span aria-hidden="true" /> Instalação
          </p>
          <h2 id="installation-title">Do download à primeira recarga</h2>
          <p>
            A instalação direta leva poucos passos. As telas podem variar conforme a versão do
            Android e o fabricante do aparelho.
          </p>
        </div>

        <ol className="installation__steps" aria-label="Como instalar">
          {installationSteps.map((step, index) => (
            <li key={step.title}>
              <span className="installation__number" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <aside className="download-note" aria-label="Aviso de instalação">
        <ShieldIcon />
        <div>
          <strong>O Android pode exibir um aviso de segurança.</strong>
          <p>
            Isso acontece porque o aplicativo é distribuído diretamente, fora da Play Store.
            Confirme que o arquivo veio deste site antes de continuar.
          </p>
        </div>
      </aside>

      <footer className="download-footer">
        <span>ChargeGrid</span>
        <p>Mobilidade elétrica com operação inteligente.</p>
        <span>Android · distribuição direta</span>
      </footer>
    </main>
  )
}
