import { useState } from 'react'
import LoginScreen from './LoginScreen'
import SignUpScreen from './SignUpScreen'

/**
 * A porta de entrada: entrar ou criar conta.
 *
 * O estado mora aqui, e não dentro de uma das telas, porque as duas são
 * irmãs — cada uma leva à outra. Pendurar o modo no `LoginScreen` faria a tela
 * de login renderizar a de cadastro, que é uma hierarquia que não corresponde a
 * nada.
 *
 * Sem navegador de propósito: `App.tsx` só monta a pilha depois de
 * autenticado (`status !== 'authenticated'` devolve isto aqui direto), então
 * não há stack para empilhar.
 */
export default function Entrada() {
  const [criando, setCriando] = useState(false)

  return criando ? (
    <SignUpScreen aoVoltar={() => setCriando(false)} />
  ) : (
    <LoginScreen aoCriarConta={() => setCriando(true)} />
  )
}
