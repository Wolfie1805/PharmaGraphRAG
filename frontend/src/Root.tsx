import React, { useEffect, useState } from 'react';
import { LandingPage } from './components/LandingPage';
import { App } from './App';

interface RootProps {
  initialHash?: string;
}

function parseHash(hash: string): { route: 'landing' | 'app'; question: string } {
  const normalized = hash.startsWith('#') ? hash.slice(1) : hash;
  const pathAndQuery = normalized.startsWith('/') ? normalized : `/${normalized}`;
  const [path, search] = pathAndQuery.split('?');

  if (path === '/app') {
    const params = new URLSearchParams(search || '');
    const q = params.get('q') || '';
    return { route: 'app', question: q };
  }

  return { route: 'landing', question: '' };
}

export const Root: React.FC<RootProps> = ({ initialHash }) => {
  const [currentHash, setCurrentHash] = useState<string>(() => {
    if (initialHash !== undefined) return initialHash;
    if (typeof window !== 'undefined') return window.location.hash || '#/';
    return '#/';
  });

  useEffect(() => {
    if (initialHash !== undefined) return;
    const handleHashChange = () => {
      setCurrentHash(window.location.hash || '#/');
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [initialHash]);

  const { route, question } = parseHash(currentHash);

  if (route === 'app') {
    return <App initialQuestion={question} />;
  }

  return <LandingPage />;
};

export default Root;
