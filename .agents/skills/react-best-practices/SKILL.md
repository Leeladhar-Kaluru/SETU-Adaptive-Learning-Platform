---
name: react-best-practices
description: Core guidelines for React 19 and TypeScript architecture, eliminating waterfalls, optimizing rendering, and managing offline state.
---

# React Best Practices Skill

1. Eliminate request waterfalls: parallelize non-dependent API calls; lift state carefully.
2. Direct imports and bundle optimization: avoid barrel-file bloat; import specifically from modules.
3. Proper state separation:
   - Server state: managed via lightweight hooks/services with explicit loading, success, and error types.
   - Offline persistent state: IndexedDB via Dexie with reactive live queries (`useLiveQuery`).
   - UI ephemeral state: React `useState` / `useReducer`.
4. Pure component rendering: avoid unnecessary `useEffect` dependencies, memoize heavy computations with `useMemo`, stabilize event handlers with `useCallback` where passed to pure children.
5. Accessible interactive controls: all buttons, dialogs, tabs, and quiz options must be keyboard navigable, have clear ARIA attributes, and visible focus indicators.
