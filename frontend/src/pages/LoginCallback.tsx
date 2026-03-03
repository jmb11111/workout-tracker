import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { handleCallback } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import LoadingSpinner from '../components/LoadingSpinner';

export default function LoginCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      setError('No authorization code received.');
      return;
    }

    handleCallback(code)
      .then((resp) => {
        setToken(resp.access_token, resp.expires_in, resp.refresh_token);
        navigate('/', { replace: true });
      })
      .catch((err) => {
        console.error('Login callback failed:', err);
        setError(err.message || 'Authentication failed.');
      });
  }, [searchParams, setToken, navigate]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-20 text-center">
        <p className="mb-4 text-sm text-red-500">{error}</p>
        <button
          onClick={() => navigate('/', { replace: true })}
          className="min-h-[44px] rounded-xl bg-blue-500 px-6 py-2.5 text-sm font-semibold text-white"
        >
          Go Home
        </button>
      </div>
    );
  }

  return (
    <div className="flex justify-center py-20">
      <LoadingSpinner message="Signing in..." />
    </div>
  );
}
