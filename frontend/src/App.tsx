import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AskProvider } from './features/ask/AskContext'
import { AboutPage } from './pages/AboutPage'
import { AskPage } from './pages/AskPage'
import { EvalPage } from './pages/EvalPage'

export default function App() {
  return (
    <AskProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<AskPage />} />
          <Route path="eval" element={<EvalPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="*" element={<AskPage />} />
        </Route>
      </Routes>
    </AskProvider>
  )
}
