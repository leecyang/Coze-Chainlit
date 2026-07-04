import { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { LoginForm } from '@/components/LoginForm';
import { useTheme } from '@/components/ThemeProvider';

import { useQuery } from 'hooks/query';

import { ChainlitContext, useAuth } from '@chainlit/react-client';

export const LoginError = new Error(
  'Error logging in. Please try again later.'
);

export default function Login() {
  const query = useQuery();
  const { data: config, user, setUserFromAPI } = useAuth();
  const [error, setError] = useState('');
  const apiClient = useContext(ChainlitContext);
  const navigate = useNavigate();
  const { variant } = useTheme();
  const isDarkMode = variant === 'dark';

  const handleCookieAuth = (json: any): void => {
    if (json?.success != true) throw LoginError;

    // Validate login cookie and get user data.
    setUserFromAPI();
  };

  const handleAuth = async (
    jsonPromise: Promise<any>,
    redirectURL?: string
  ) => {
    try {
      const json = await jsonPromise;

      handleCookieAuth(json);

      if (redirectURL) {
        navigate(redirectURL);
      }
    } catch (error: any) {
      setError(error.message);
    }
  };

  const handleHeaderAuth = async () => {
    const jsonPromise = apiClient.headerAuth();

    // Why does apiClient redirect to '/' but handlePasswordLogin to callbackUrl?
    await handleAuth(jsonPromise, '/');
  };

  const handlePasswordLogin = async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    const jsonPromise = apiClient.passwordAuth(formData);
    await handleAuth(jsonPromise);
  };

  useEffect(() => {
    setError(query.get('error') || '');
  }, [query]);

  useEffect(() => {
    if (!config) {
      return;
    }
    if (!config.requireLogin) {
      navigate('/');
    }
    if (config.headerAuth && !user) {
      handleHeaderAuth();
    }
    if (user) {
      navigate('/');
    }
  }, [config, user]);

  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-center gap-2 md:justify-start">
          <img
            src="/public/logo_full_text.svg"
            alt="灵犀智学"
            className="h-12 w-auto"
            draggable={false}
          />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm">
            <div className="mb-8 space-y-2">
              <h1 className="text-3xl font-semibold tracking-normal">
                灵犀智学
              </h1>
              <p className="text-sm text-muted-foreground">
                面向计算机三级网络技术学习场景的智能对话与练习系统
              </p>
            </div>
            <LoginForm
              error={error}
              callbackUrl="/"
              providers={config?.oauthProviders || []}
              onPasswordSignIn={
                config?.passwordAuth ? handlePasswordLogin : undefined
              }
              onOAuthSignIn={async (provider: string) => {
                window.location.href = apiClient.getOAuthEndpoint(provider);
              }}
            />
          </div>
        </div>
      </div>
      {!config?.headerAuth ? (
        <div className="relative hidden bg-muted lg:block overflow-hidden">
          <img
            src={
              config?.ui?.login_page_image ||
              '/public/hero.png'
            }
            alt="灵犀智学登录背景"
            className={`absolute inset-0 h-full w-full object-cover ${
              isDarkMode
                ? config?.ui?.login_page_image_dark_filter ||
                  'brightness-[0.2] grayscale'
                : config?.ui?.login_page_image_filter || ''
            }`}
          />
        </div>
      ) : null}
    </div>
  );
}
