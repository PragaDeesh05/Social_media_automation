import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { ContentAssetsPage } from './features/content-assets/ContentAssetsPage';
import { VideoGenerationPage } from './features/video-gen/VideoGenerationPage';
import { CarouselGenerationPage } from './features/carousel-gen/CarouselGenerationPage';
import { PosterGenerationPage } from './features/poster-gen/PosterGenerationPage';
import { CalendarPage } from './features/content-calendar/CalendarPage';
import { PublishingQueuePage } from './features/publishing/PublishingQueuePage';
import { MediaLibraryPage } from './features/media-library/MediaLibraryPage';
import { AnalyticsPage } from './features/analytics/AnalyticsPage';
import { CreateCampaignPage } from './features/campaigns/CreateCampaignPage';
import { SourceAnalysisPage } from './features/uploads/SourceAnalysisPage';
import { PrivacyPolicyPage } from './features/legal/PrivacyPolicyPage';
import { TermsOfServicePage } from './features/legal/TermsOfServicePage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/privacy" element={<PrivacyPolicyPage />} />
        <Route path="/terms" element={<TermsOfServicePage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assets" element={<ContentAssetsPage />} />
          <Route path="video-gen" element={<VideoGenerationPage />} />
          <Route path="carousel-gen" element={<CarouselGenerationPage />} />
          <Route path="poster-gen" element={<PosterGenerationPage />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="publishing" element={<PublishingQueuePage />} />
          <Route path="media" element={<MediaLibraryPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="create" element={<CreateCampaignPage />} />
          <Route path="sources" element={<SourceAnalysisPage />} />
          {/* Legacy redirects */}
          <Route path="connected-accounts" element={<Navigate to="/publishing" replace />} />
          <Route path="settings" element={<Navigate to="/assets" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
