import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Calendar, Video, Layers, Image as ImageIcon,
  Clock, BarChart3, Activity, Sparkles, Plus, CheckCircle2, Film
} from 'lucide-react';
import { YoutubeIcon, InstagramIcon, FacebookIcon } from './SocialIcons';
import { api } from '../services/api';

export const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'degraded' | 'checking'>('checking');
  const [assetCount, setAssetCount] = useState<number>(0);
  const [queueCount, setQueueCount] = useState<number>(0);

  useEffect(() => {
    api.getHealth()
      .then((res) => setHealthStatus(res.status))
      .catch(() => setHealthStatus('degraded'));

    // Fetch quick stats for badges
    api.listAssets()
      .then((res) => setAssetCount(res?.length || 0))
      .catch(() => {});

    api.getPublishingQueue('scheduled')
      .then((res) => setQueueCount(res?.length || 0))
      .catch(() => {});
  }, [location.pathname]);

  const workspaceNav = [
    { to: '/', label: 'Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
    { to: '/assets', label: 'Content Assets', icon: <Layers className="w-4 h-4" />, count: assetCount },
    { to: '/calendar', label: 'Content Calendar', icon: <Calendar className="w-4 h-4" /> },
    { to: '/publishing', label: 'Publishing Queue', icon: <Clock className="w-4 h-4" />, count: queueCount },
    { to: '/media', label: 'Media Library', icon: <Film className="w-4 h-4" /> },
    { to: '/analytics', label: 'Analytics', icon: <BarChart3 className="w-4 h-4" /> },
  ];

  const studiosNav = [
    { to: '/video-gen', label: 'Video Studio', icon: <Video className="w-4 h-4" />, badge: '9:16 HD' },
    { to: '/carousel-gen', label: 'Carousel Studio', icon: <Layers className="w-4 h-4" />, badge: 'SVG' },
    { to: '/poster-gen', label: 'Poster Studio', icon: <ImageIcon className="w-4 h-4" />, badge: 'Vector' },
  ];

  const getPageTitle = () => {
    const allItems = [...workspaceNav, ...studiosNav];
    const match = allItems.find(i => i.to === location.pathname);
    if (match) return match.label;
    if (location.pathname.startsWith('/video-gen')) return 'Video Studio (9:16 Ad Maker)';
    if (location.pathname.startsWith('/carousel-gen')) return 'Carousel Studio (Animated SVG)';
    if (location.pathname.startsWith('/poster-gen')) return 'Poster Studio (Vector Graphic)';
    if (location.pathname.startsWith('/create')) return 'AI Campaign Generator';
    return 'Content Engine';
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC] text-slate-800 font-sans antialiased overflow-hidden">
      {/* Slate Navy Sidebar */}
      <aside className="w-64 bg-[#1E293B] flex flex-col border-r border-slate-700/80 shadow-2xl z-20 shrink-0">
        {/* Brand Header */}
        <div className="h-16 px-5 flex items-center justify-between border-b border-slate-700/60 bg-[#0F172A]/80">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <span className="text-white font-black text-lg tracking-wider">iB</span>
            </div>
            <div>
              <span className="text-white font-bold tracking-tight text-base leading-none block">IncuBrix</span>
              <span className="text-indigo-400 text-[11px] block font-mono font-medium mt-0.5">Content Engine</span>
            </div>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="flex-1 px-3 py-4 space-y-6 overflow-y-auto custom-scrollbar">
          {/* Section: WORKSPACE */}
          <div>
            <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Workspace
            </div>
            <nav className="space-y-1">
              {workspaceNav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/30'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700/40'
                    }`
                  }
                >
                  <div className="flex items-center space-x-3">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                  {item.count !== undefined && item.count > 0 && (
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full bg-slate-700/60 text-slate-300">
                      {item.count}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Section: CREATIVE STUDIOS */}
          <div>
            <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>Creative Studios</span>
              <Sparkles className="w-3 h-3 text-indigo-400" />
            </div>
            <nav className="space-y-1">
              {studiosNav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/30'
                        : 'text-slate-300 hover:text-white hover:bg-slate-700/40'
                    }`
                  }
                >
                  <div className="flex items-center space-x-3">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>

        {/* Sidebar Footer: System Status & Connected Accounts */}
        <div className="p-4 border-t border-slate-700/60 bg-[#0F172A]/90">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-400 flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-slate-400" />
              <span>Engine Status</span>
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${
                healthStatus === 'healthy'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  healthStatus === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`}
              />
              {healthStatus.toUpperCase()}
            </span>
          </div>

          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
            <span className="text-[10px] uppercase font-bold text-slate-500">Connected</span>
            <div className="flex items-center space-x-2">
              <span className="flex items-center space-x-1 text-slate-300" title="YouTube connected">
                <YoutubeIcon className="w-3.5 h-3.5 text-rose-500" />
              </span>
              <span className="flex items-center space-x-1 text-slate-300" title="Facebook connected">
                <FacebookIcon className="w-3.5 h-3.5 text-blue-500" />
              </span>
              <span className="flex items-center space-x-1 text-slate-300" title="Instagram connected">
                <InstagramIcon className="w-3.5 h-3.5 text-pink-500" />
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main App Layout */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-16 bg-white border-b border-slate-200/90 px-8 flex items-center justify-between shadow-xs z-10 shrink-0">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400 font-medium">IncuBrix Content Engine</span>
            <span className="text-slate-300">/</span>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight">
              {getPageTitle()}
            </h1>
          </div>

          <div className="flex items-center space-x-4">
            {/* Connected Platform Status Chips */}
            <div className="hidden md:flex items-center space-x-2">
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                <YoutubeIcon className="w-3 h-3 text-rose-600" />
                <span>YouTube</span>
                <CheckCircle2 className="w-3 h-3 text-rose-600" />
              </span>
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
                <FacebookIcon className="w-3 h-3 text-blue-600" />
                <span>Facebook</span>
                <CheckCircle2 className="w-3 h-3 text-blue-600" />
              </span>
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-pink-50 text-pink-700 border border-pink-200">
                <InstagramIcon className="w-3 h-3 text-pink-600" />
                <span>Instagram</span>
                <CheckCircle2 className="w-3 h-3 text-pink-600" />
              </span>
            </div>

            {/* Quick Actions */}
            <button
              onClick={() => navigate('/create')}
              className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create Campaign</span>
            </button>
          </div>
        </header>

        {/* Content Outlet */}
        <main className="flex-1 overflow-y-auto bg-[#F8FAFC] p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};