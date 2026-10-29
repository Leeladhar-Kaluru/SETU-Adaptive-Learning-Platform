import { useCallback, useEffect, useState } from 'react';
import {
  api,
  CatalogueBoard,
  CatalogueLanguage,
  CatalogueSubject,
} from '../services/api';

export function useTaxonomy(enabled = true) {
  const [boards, setBoards] = useState<CatalogueBoard[]>([]);
  const [subjects, setSubjects] = useState<CatalogueSubject[]>([]);
  const [languages, setLanguages] = useState<CatalogueLanguage[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([api.getBoards(), api.getSubjects(), api.getLanguages()])
      .then(([boardRows, subjectRows, languageRows]) => {
        if (cancelled) return;
        setBoards(boardRows);
        setSubjects(subjectRows);
        setLanguages(languageRows);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load boards, subjects, and languages.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, reloadToken]);

  const retry = useCallback(() => setReloadToken((value) => value + 1), []);

  return { boards, subjects, languages, loading, error, retry };
}
