import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppThemeProvider from './theme/AppThemeProvider';
import AppLayout from './layout/AppLayout';
import ErrorBanner from './components/ErrorBanner';

// Pages
import Overview from './pages/Overview';
import ListeningPatterns from './pages/ListeningPatterns';
import Discovery from './pages/Discovery';
import Milestones from './pages/Milestones';
import Sessions from './pages/Sessions';
import Recommendations from './pages/Recommendations';
import Simulator from './pages/Simulator';
import NotFound from './pages/NotFound';

function App() {
  return (
    <AppThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Overview />} />
            <Route path="listening-patterns" element={<ListeningPatterns />} />
            <Route path="discovery" element={<Discovery />} />
            <Route path="milestones" element={<Milestones />} />
            <Route path="sessions" element={<Sessions />} />
            <Route path="recommendations" element={<Recommendations />} />
            <Route path="simulator" element={<Simulator />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
        <ErrorBanner />
      </BrowserRouter>
    </AppThemeProvider>
  );
}

export default App;
