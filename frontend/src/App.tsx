import { Boxes, LayoutDashboard, PlugZap, Settings, Sparkles } from 'lucide-react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { McpPage } from './pages/McpPage'
import { OverviewPage } from './pages/OverviewPage'
import { ResourcesPage } from './pages/ResourcesPage'
import { SettingsPage } from './pages/SettingsPage'
import { ChatPage } from './pages/ChatPage'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/resources', label: 'Resources', icon: Boxes },
  { to: '/assistant', label: 'Ask AI', icon: Sparkles },
  { to: '/mcp', label: 'MCP tools', icon: PlugZap },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function App() {
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span>O</span><strong>OpsLens</strong></div><nav>{nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? 'active' : ''}><Icon size={17} />{label}</NavLink>)}</nav><p className="sidebar-note">Local · read-only</p></aside>
    <main className="main-content"><Routes><Route path="/" element={<OverviewPage />} /><Route path="/resources" element={<ResourcesPage />} /><Route path="/assistant" element={<ChatPage />} /><Route path="/mcp" element={<McpPage />} /><Route path="/settings" element={<SettingsPage />} /></Routes></main>
  </div>
}
