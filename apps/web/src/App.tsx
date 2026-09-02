import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppThemeProvider from './theme/AppThemeProvider';
import AppLayout from './layout/AppLayout';
import ErrorBanner from './components/ErrorBanner';

// Pages
import Insights from './pages/Insights';
import Recommendations from './pages/Recommendations';
import DataHealth from './pages/DataHealth';
import NotFound from './pages/NotFound';

function App() {
  return (
    <AppThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Insights />} />
            <Route path="recommendations" element={<Recommendations />} />
            <Route path="data-health" element={<DataHealth />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
        <ErrorBanner />
      </BrowserRouter>
    </AppThemeProvider>
  );
}

export default App;
