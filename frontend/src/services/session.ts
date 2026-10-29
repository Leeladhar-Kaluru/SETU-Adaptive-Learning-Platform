export const ACTIVE_USER_KEY = 'setu_active_user_id';

export function getActiveUserId(): string | null {
  return localStorage.getItem(ACTIVE_USER_KEY);
}

export function setActiveUserId(userId: string): void {
  localStorage.setItem(ACTIVE_USER_KEY, userId);
}

export function clearActiveUserId(): void {
  localStorage.removeItem(ACTIVE_USER_KEY);
}
