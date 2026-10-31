/**
 * Role → UI access map. Mirrors the backend role map (plans, M16); the
 * backend still enforces every rule, this only hides what a role can't use.
 */

export type Role = 'purchasing' | 'owner' | 'finance'

export type NavTab = 'Today' | 'Quick check' | 'History' | 'Import' | 'Audit Log'

const TAB_HASH: Record<NavTab, string> = {
  'Today': '#today',
  'Quick check': '#quick-check',
  'History': '#history',
  'Import': '#import',
  'Audit Log': '#audit',
}

const TABS_BY_ROLE: Record<Role, NavTab[]> = {
  purchasing: ['Today', 'Quick check', 'History', 'Import'],
  owner: ['Today', 'History', 'Audit Log'],
  finance: ['Today', 'History', 'Audit Log'],
}

// Review (owner) and Payments (finance) pages arrive in M19 / M24; until then
// owner lands on Today, where approve/return live, and finance on History.
const LANDING_BY_ROLE: Record<Role, string> = {
  purchasing: '#today',
  owner: '#today',
  finance: '#history',
}

function asRole(role: string | null | undefined): Role | null {
  return role === 'purchasing' || role === 'owner' || role === 'finance' ? role : null
}

export function tabToHash(tab: NavTab): string {
  return TAB_HASH[tab]
}

export function tabsFor(role: string | null | undefined): NavTab[] {
  const r = asRole(role)
  return r ? TABS_BY_ROLE[r] : ['Today']
}

export function landingHash(role: string | null | undefined): string {
  const r = asRole(role)
  return r ? LANDING_BY_ROLE[r] : '#today'
}

export function canOpenHash(role: string | null | undefined, hash: string): boolean {
  return tabsFor(role).some((tab) => TAB_HASH[tab] === hash)
}

export function canAddRequests(role: string | null | undefined): boolean {
  return role === 'purchasing' || role === 'owner'
}

export function canRecheck(role: string | null | undefined): boolean {
  return role === 'purchasing' || role === 'owner'
}
