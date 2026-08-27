import { Text } from 'react-native'
import { NavigationContainer, DarkTheme, type Theme } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { AuthProvider, useAuth } from './src/auth'
import { Carregando } from './src/components'
import LoginScreen from './src/screens/LoginScreen'
import MapScreen from './src/screens/MapScreen'
import SessionScreen from './src/screens/SessionScreen'
import StationScreen from './src/screens/StationScreen'
import ReservationsScreen from './src/screens/ReservationsScreen'
import NewReservationScreen from './src/screens/NewReservationScreen'
import ScannerScreen from './src/screens/ScannerScreen'
import HistoryScreen from './src/screens/HistoryScreen'
import ProfileScreen from './src/screens/ProfileScreen'
import type { Abas, RotasApp } from './src/navigation'
import { cores } from './src/theme'

const Stack = createNativeStackNavigator<RotasApp>()
const Tab = createBottomTabNavigator<Abas>()

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

// Ícones em texto: manter o app sem biblioteca de ícones evita mais um módulo
// nativo por quatro glifos. Se a barra crescer, vale trocar por @expo/vector-icons.
const ICONE: Record<keyof Abas, string> = {
  Mapa: '◎',
  Agenda: '▣',
  Historico: '≡',
  Perfil: '◍'
}

const ROTULO: Record<keyof Abas, string> = {
  Mapa: 'Mapa',
  Agenda: 'Agenda',
  Historico: 'Histórico',
  Perfil: 'Perfil'
}

function Abas() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: { backgroundColor: cores.superficie, borderTopColor: cores.borda },
        tabBarActiveTintColor: cores.acento,
        tabBarInactiveTintColor: cores.textoFraco,
        tabBarLabel: ROTULO[route.name],
        tabBarIcon: ({ color }) => (
          <Text style={{ color, fontSize: 18, lineHeight: 22 }}>{ICONE[route.name]}</Text>
        )
      })}
    >
      <Tab.Screen name="Mapa" component={MapScreen} />
      <Tab.Screen name="Agenda" component={ReservationsScreen} />
      <Tab.Screen name="Historico" component={HistoryScreen} />
      <Tab.Screen name="Perfil" component={ProfileScreen} />
    </Tab.Navigator>
  )
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
      <Stack.Screen name="Abas" component={Abas} options={{ headerShown: false }} />
      <Stack.Screen name="Estacao" component={StationScreen} />
      <Stack.Screen name="Sessao" component={SessionScreen} options={{ title: 'Minha recarga' }} />
      <Stack.Screen
        name="NovoAgendamento"
        component={NewReservationScreen}
        options={{ title: 'Agendar recarga' }}
      />
      <Stack.Screen
        name="Escanear"
        component={ScannerScreen}
        options={{ title: 'Ler QR do carregador' }}
      />
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
