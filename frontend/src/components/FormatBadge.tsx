import React from 'react';
import { ContentFormat } from '../types';
import { FileText, Image as ImageIcon, Layers, Video } from 'lucide-react';

interface FormatBadgeProps {
  format: ContentFormat;
}

export const FormatBadge: React.FC<FormatBadgeProps> = ({ format }) => {
  const configs: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    text: { label: 'Text Post', icon: <FileText className="w-3 h-3 mr-1" />, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
    image: { label: 'Graphic / Card', icon: <ImageIcon className="w-3 h-3 mr-1" />, color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
    carousel: { label: '5-Slide Carousel', icon: <Layers className="w-3 h-3 mr-1" />, color: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
    short_video: { label: 'Short Video (<=60s)', icon: <Video className="w-3 h-3 mr-1" />, color: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
    reel: { label: 'Instagram Reel', icon: <Video className="w-3 h-3 mr-1" />, color: 'text-pink-400 bg-pink-500/10 border-pink-500/20' },
    shorts: { label: 'YouTube Short', icon: <Video className="w-3 h-3 mr-1" />, color: 'text-red-400 bg-red-500/10 border-red-500/20' },
  };

  const c = configs[format] || { label: format, icon: null, color: 'text-slate-400 bg-slate-800 border-slate-700' };

  return (
    <span className={`inline-flex items-center text-xs px-2.5 py-0.5 rounded-md font-medium border ${c.color}`}>
      {c.icon}
      {c.label}
    </span>
  );
};
