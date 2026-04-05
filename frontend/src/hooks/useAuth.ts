import { useState, useEffect, useCallback } from 'react';
import { getLoginUrl } from '../api/client';

interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  loading: boolean;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    token: null,
    loading: true,
  });

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const expiresAt = localStorage.getItem('token_expires_at');

    if (token) {
      // Check if token has expired
      if (expiresAt) {
        const expiry = parseInt(expiresAt, 10);
        if (Date.now() > expiry) {
          // Token expired — try refresh or clear
          const refreshTokenStr = localStorage.getItem('refresh_token');
          if (refreshTokenStr) {
            // Attempt refresh in background
            import('../api/client').then(({ refreshToken }) => {
              refreshToken(refreshTokenStr)
                .then((resp) => {
                  localStorage.setItem('access_token', resp.access_token);
                  if (resp.refresh_token) {
                    localStorage.setItem('refresh_token', resp.refresh_token);
                  }
                  if (resp.expires_in) {
                    localStorage.setItem(
                      'token_expires_at',
                      String(Date.now() + resp.expires_in * 1000),
                    );
                  }
                  setState({
                    isAuthenticated: true,
                    token: resp.access_token,
                    loading: false,
                  });
                })
                .catch(() => {
                  localStorage.removeItem('access_token');
                  localStorage.removeItem('refresh_token');
                  localStorage.removeItem('token_expires_at');
                  setState({ isAuthenticated: false, token: null, loading: false });
                });
            });
            return;
          } else {
            localStorage.removeItem('access_token');
            localStorage.removeItem('token_expires_at');
            setState({ isAuthenticated: false, token: null, loading: false });
            return;
          }
        }
      }

      setState({ isAuthenticated: true, token, loading: false });
    } else {
      // No token — auto-login if we haven't already tried this session
      const triedAutoLogin = sessionStorage.getItem('tried_auto_login');
      if (!triedAutoLogin) {
        sessionStorage.setItem('tried_auto_login', '1');
        // Kick off OIDC flow — if user has an Authentik session it'll be seamless
        import('../api/client').then(({ getLoginUrl }) => {
          getLoginUrl()
            .then(({ authorization_url }) => {
              window.location.href = authorization_url;
            })
            .catch(() => {
              setState({ isAuthenticated: false, token: null, loading: false });
            });
        });
        return;
      }
      setState({ isAuthenticated: false, token: null, loading: false });
    }
  }, []);

  const [loginError, setLoginError] = useState<string | null>(null);

  const login = useCallback(async () => {
    setLoginError(null);
    try {
      const { authorization_url } = await getLoginUrl();
      window.location.href = authorization_url;
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to start sign-in';
      if (message.includes('not configured') || message.includes('503')) {
        setLoginError('Sign-in is not configured yet. An OIDC provider needs to be set up.');
      } else {
        setLoginError(message);
      }
    }
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expires_at');
    sessionStorage.removeItem('tried_auto_login');
    setState({ isAuthenticated: false, token: null, loading: false });
    // Redirect to Authentik end_session to kill SSO session too
    try {
      const resp = await fetch('/api/auth/logout-url');
      const data = await resp.json();
      if (data.logout_url && data.logout_url !== '/') {
        window.location.href = data.logout_url;
        return;
      }
    } catch {
      // Fall through to local logout
    }
    window.location.href = '/';
  }, []);

  const setToken = useCallback(
    (accessToken: string, expiresIn?: number | null, refreshTokenStr?: string | null) => {
      localStorage.setItem('access_token', accessToken);
      if (refreshTokenStr) {
        localStorage.setItem('refresh_token', refreshTokenStr);
      }
      if (expiresIn) {
        localStorage.setItem(
          'token_expires_at',
          String(Date.now() + expiresIn * 1000),
        );
      }
      // Clear auto-login flag on successful auth
      sessionStorage.removeItem('tried_auto_login');
      setState({ isAuthenticated: true, token: accessToken, loading: false });
    },
    [],
  );

  return {
    isAuthenticated: state.isAuthenticated,
    token: state.token,
    loading: state.loading,
    loginError,
    login,
    logout,
    setToken,
  };
}
