import { createContext, useContext } from 'react'
// App supplies the authenticated role; default permits standalone component fixtures.
export const RoleContext = createContext<'viewer' | 'operator' | 'admin'>('admin')
export function useCanEdit() { return useContext(RoleContext) !== 'viewer' }

export function useIsAdmin() { return useContext(RoleContext) === 'admin' }
