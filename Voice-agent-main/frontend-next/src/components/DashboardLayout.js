'use client';
import { useAuth, clientProfile } from '../context/AuthContext';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { 
  Activity, 
  Rocket, 
  Bot, 
  BrainCircuit, 
  Building2, 
  ClipboardEdit, 
  ShieldCheck, 
  Phone, 
  PhoneCall,
  Home, 
  PlaySquare, 
  BarChart3, 
  LogOut,
  GitBranch,
  Layers,
  Wrench,
  CheckSquare,
  FileSpreadsheet,
  Globe,
  Settings as SettingsIcon,
  Sliders,
  ChevronRight,
  Zap
} from 'lucide-react';

const CRM_READINESS_UI_ENABLED = process.env.NEXT_PUBLIC_CRM_READINESS_UI_ENABLED === 'true';
const SCRAPE_GENERATE_SCRIPT_ENABLED = process.env.NEXT_PUBLIC_SCRAPE_GENERATE_SCRIPT_ENABLED === 'true';

export default function DashboardLayout({ children }) {
  const { currentRole, activeClient, setActiveClient, logout, user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !currentRole) router.push('/login');
  }, [loading, currentRole, router]);

  if (loading || !currentRole || !user) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#09090B' }}>
        <div className="scrape-loading-dot" style={{ background: '#3B82F6', width: '12px', height: '12px' }} />
      </div>
    );
  }

  // ── Retell-Inspired Main Navigation ─────────────────────────────────
  const sidebarGroups = [
    {
      title: "VOICE AGENT PLATFORM",
      items: [
        { label: "Voice Agents", path: "/agents", icon: <Bot size={17} /> },
        { label: "Call History & Logs", path: "/logs", icon: <PhoneCall size={17} /> },
        { label: "Analytics & Results", path: "/results", icon: <BarChart3 size={17} /> },
        { label: "Outbound Campaigns", path: "/campaigns", icon: <Rocket size={17} /> },
        { label: "Phone Numbers", path: "/numbers", icon: <Phone size={17} /> },
        ...(SCRAPE_GENERATE_SCRIPT_ENABLED ? [{ label: "Knowledge Base", path: "/intelligence", icon: <BrainCircuit size={17} /> }] : []),
        { label: "Live Playground", path: "/talk-live", icon: <PlaySquare size={17} /> },
        ...(CRM_READINESS_UI_ENABLED ? [{ label: "CRM Integrations", path: "/crm-readiness", icon: <ShieldCheck size={17} /> }] : []),
      ]
    },
    {
      title: "WORKSPACE",
      items: [
        ...(currentRole === 'admin' ? [{ label: "Clients & Tenants", path: "/clients", icon: <Building2 size={17} /> }] : []),
        { label: "Client Dashboard", path: "/client-dashboard", icon: <Home size={17} /> },
      ]
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#09090B', color: '#F4F4F5', fontFamily: "var(--font-sans, sans-serif)" }}>
      
      {/* ── Retell AI Top Header Bar ── */}
      <header style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '0 24px', height: '56px',
        background: '#121215',
        borderBottom: '1px solid #222226',
        flexShrink: 0,
        zIndex: 50
      }}>
        {/* Brand Logo & Platform Version */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }} onClick={() => router.push('/agents')}>
            <div style={{ padding: '6px', borderRadius: '8px', background: 'linear-gradient(135deg, #3B82F6, #1D4ED8)', color: '#FFF' }}>
              <Zap size={18} fill="#FFF" />
            </div>
            <span style={{ fontSize: '16px', fontWeight: 800, letterSpacing: '-0.3px', color: '#FFFFFF' }}>
              Retell<span style={{ color: '#60A5FA', fontWeight: 600 }}>Voice</span>
            </span>
          </div>
          
          <span style={{
            padding: '2px 8px',
            border: '1px solid #2A2A32',
            borderRadius: '12px',
            fontSize: '11px',
            fontWeight: '700',
            color: '#60A5FA',
            background: 'rgba(59, 130, 246, 0.12)',
            fontFamily: 'monospace'
          }}>
            R4 Pro Engine
          </span>
        </div>

        {/* Top Right User & Client Profile Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {currentRole === 'admin' && (
            <select
              style={{
                background: '#1A1A1E',
                border: '1px solid #2A2A32',
                color: '#FFFFFF',
                fontSize: '12px',
                fontWeight: '600',
                borderRadius: '6px',
                padding: '6px 12px',
                outline: 'none',
                width: '200px',
                cursor: 'pointer'
              }}
              value={activeClient}
              onChange={(e) => setActiveClient(e.target.value)}
            >
              {Object.keys(clientProfile).map(key => (
                <option key={key} value={key}>Tenant: {clientProfile[key].name}</option>
              ))}
            </select>
          )}

          {/* User Profile Tag */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {user.photoURL ? (
              <img
                src={user.photoURL}
                alt={user.name}
                referrerPolicy="no-referrer"
                style={{ width: '30px', height: '30px', borderRadius: '50%', objectFit: 'cover', border: '1px solid #33333B' }}
              />
            ) : (
              <div style={{
                width: '30px', height: '30px', borderRadius: '50%',
                background: '#1F1F24', border: '1px solid #33333B',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 700, color: '#60A5FA'
              }}>
                {user.initials}
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#FFFFFF' }}>{user.name}</span>
              <span style={{ fontSize: '10px', color: '#A3A3A3', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{currentRole} Access</span>
            </div>
          </div>

          {/* Logout Button */}
          <button
            onClick={logout}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 12px',
              background: 'none',
              border: '1px solid #2A2A32',
              color: '#A3A3A3',
              fontSize: '12px',
              fontWeight: '600',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 100ms ease-out'
            }}
            onMouseEnter={e => { e.currentTarget.style.color = '#FFFFFF'; e.currentTarget.style.borderColor = '#3B82F6'; }}
            onMouseLeave={e => { e.currentTarget.style.color = '#A3A3A3'; e.currentTarget.style.borderColor = '#2A2A32'; }}
          >
            <LogOut size={14} /> Sign Out
          </button>
        </div>
      </header>

      {/* ── Main Layout Body ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* ── Retell-Style Left Sidebar Navigation ── */}
        <aside style={{
          background: '#0E0E10',
          borderRight: '1px solid #1E1E22',
          display: 'flex',
          flexDirection: 'column',
          width: '230px',
          flexShrink: 0
        }}>
          <nav style={{ flex: 1, padding: '16px 10px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {sidebarGroups.map(group => (
              <div key={group.title}>
                <div style={{
                  fontSize: '10px',
                  fontWeight: '800',
                  color: '#52525B',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  padding: '0 10px 8px 10px'
                }}>
                  {group.title}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {group.items.map(item => {
                    const isActive = pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path) && item.path !== '/agents');
                    return (
                      <Link
                        key={item.path + item.label}
                        href={item.path}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          textDecoration: 'none',
                          fontSize: '13px',
                          fontWeight: isActive ? '700' : '500',
                          color: isActive ? '#60A5FA' : '#A1A1AA',
                          background: isActive ? 'rgba(59, 130, 246, 0.14)' : 'transparent',
                          border: isActive ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
                          transition: 'all 100ms ease-out'
                        }}
                        onMouseEnter={e => {
                          if (!isActive) {
                            e.currentTarget.style.background = '#18181B';
                            e.currentTarget.style.color = '#FFFFFF';
                          }
                        }}
                        onMouseLeave={e => {
                          if (!isActive) {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = '#A1A1AA';
                          }
                        }}
                      >
                        <span style={{ color: isActive ? '#60A5FA' : '#71717A', display: 'flex', alignItems: 'center' }}>
                          {item.icon}
                        </span>
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* ── Main Content Area ── */}
        <main style={{ flex: 1, padding: '0', overflowY: 'auto', background: '#09090B' }}>
          {children}
        </main>
      </div>
    </div>
  );
}
