import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import TodayPage from './pages/TodayPage';
import HistoryPage from './pages/HistoryPage';
import RecordsPage from './pages/RecordsPage';
import SearchPage from './pages/SearchPage';
import MovementDetailPage from './pages/MovementDetailPage';
import ProfilePage from './pages/ProfilePage';
import LoginCallback from './pages/LoginCallback';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<TodayPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/movement/:id" element={<MovementDetailPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
        <Route path="/auth/callback" element={<LoginCallback />} />
      </Routes>
    </BrowserRouter>
  );
}
