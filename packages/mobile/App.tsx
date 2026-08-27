import { NavigationContainer, DarkTheme, type Theme } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AuthProvider, useAuth } from './src/auth'
import { Carregando } from './src/components'
import LoginScreen from './src/screens/LoginScreen'
import MapScreen from './src/screens/MapScreen'
import SessionScreen from './src/screens/SessionScreen'
import StationScreen from './src/screens/StationScreen'
import type { RotasApp } from './src/navigation'
import { cores } from './src/theme'

const Stack = createNativeStackNavigator<RotasApp>()

const tema: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: cores.acento,
    background: cores.fundo,
    card: cores.fundo,
    text: cores.texto,
    border: cores.borda
  }
}

function Rotas() {
  const { status } = useAuth()

  // "checking" existe porque o AsyncStorage e assincrono: ate ele responder,
  // nao da para saber se o motorista ja estava logado.
  if (status === 'checking') return <Carregando rotulo="Restaurando sessao..." />

  if (status !== 'authenticated') return <LoginScreen />

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: cores.fundo },
        headerTintColor: cores.texto,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: cores.fundo }
      }}
    >
      <Stack.Screen name="Mapa" component={MapScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Estacao" component={StationScreen} />
      <Stack.Screen name="Sessao" component={SessionScreen} options={{ title: 'Minha recarga' }} />
    </Stack.Navigator>
  )
}

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer theme={tema}>
        <AuthProvider>
          <StatusBar style="light" />
          <Rotas />
        </AuthProvider>
      </NavigationContainer>
    </SafeAreaProvider>
  )
}
