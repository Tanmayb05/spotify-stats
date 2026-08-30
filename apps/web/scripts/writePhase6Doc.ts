#!/usr/bin/env node
//
// Run with:  cd apps/web && node --loader ts-node/esm scripts/writePhase6Doc.ts
//
// Writes the Phase 6 report to repo-root documentation/ via writePhaseDoc().

import { writePhaseDoc, PhaseDocParams } from './writePhaseDoc.ts';

const phase6Params: PhaseDocParams = {
  phaseNumber: 6,
  phaseName: 'ML Recommender',
  status: 'Completed',
  overview:
    'Added a content-based track recommender. Because Spotify deprecated the audio-features API (Nov 2024) and no cached features exist, each track vector is synthesised from a behavioural + metadata hybrid: the mood heuristic (valence/energy/danceability) averaged over that track\'s plays, plus track/artist popularity, follower count, duration, explicit flag, and release-year recency. Recommendations are cosine-scored against a recency-weighted preference vector and MMR-diversified, with per-track "why this" feature attribution. The Recommendations page renders the picks as a card grid with a mood filter and CSV export.',
  timeToComplete: '2 hours',
  filesCreated: [
    'apps/api/app/routes/reco.py - /api/reco and /api/export/recommendations endpoints',
    'apps/web/scripts/writePhase6Doc.ts - this documentation generator',
    'documentation/<timestamp>_phase_6_ml_recommender.md - this document',
  ],
  filesModified: [
    'apps/api/app/services/data_loader.py - added _salvage_json_array, _load_track_metadata, _build_track_vectors, get_recommendations, get_recommendations_csv_rows, and RECO_* constants',
    'apps/api/app/main.py - registered reco router',
    'apps/api/requirements.txt - added numpy and scikit-learn (already imported by data_loader)',
    'apps/web/src/types/api.ts - added Recommendation, RecommendationWhy, RecommendationsResponse, TargetMood types',
    'apps/web/src/api/client.ts - added getRecommendations and exportRecommendations',
    'apps/web/src/pages/Recommendations.tsx - full rewrite from stub to functional card grid',
  ],
  checklist: {
    'Intuitive navigation': true,
    'Consistent design': true,
    'Responsive layout': true,
    'A11y labels/roles': true,
    'Error handling & feedback': true,
    'Performance sanity checks': true,
    'Security baseline (no secrets, safe fetch, minimal data)': true,
    'Docs generated': true,
  },
  implementation: {
    purpose:
      'Surface tracks adjacent to the user\'s taste that are not already in heavy rotation, with a transparent explanation of why each was picked and an optional mood steer (happy / energetic / chill).',
    features: [
      'GET /api/reco?top_k=&target_mood= returns scored, diversified recommendations',
      'GET /api/export/recommendations streams the same list as CSV',
      'target_mood blends valence/energy/danceability of the preference vector toward a mood target',
      'why.top_features + why.summary explain each pick in plain language',
      'Recommendations page: mood filter chips (with colour dots, not colour alone), score chips, feature chips, CSV export button, skeleton and empty states',
      'Heavy-rotation favourites are damped and the top-25 most-played tracks are excluded so the list stays fresh',
    ],
    implementation: [
      'songs_info.json is a truncated write, so _salvage_json_array decodes its "songs" array element-by-element and stops at the first malformed entry (~808 tracks salvaged)',
      '_load_track_metadata caches track metadata by spotify_track_uri and artist metadata by lowercased name',
      '_build_track_vectors aggregates plays per track, averages the mood heuristic, joins metadata, and builds the raw feature matrix in RECO_FEATURE_NAMES order; result cached on the instance',
      'get_recommendations: StandardScaler -> recency-weighted preference vector (half-life 180 days, weighted by log1p(play_count)) -> optional mood blend -> cosine_similarity -> play-count damping -> exclude top-played -> greedy MMR (lambda 0.7) over the top 5*top_k candidates',
      'why.top_features are the feature dimensions whose standardised value pulls hardest in the direction of the preference vector',
      'Frontend re-fetches when the mood filter changes (useEffect dep); errors go through the zustand store to the global ErrorBanner',
      'CSV export reuses the anchor-download trick from Overview.tsx against the streaming backend endpoint',
    ],
    flow: [
      'User opens the Recommendations page',
      'Frontend calls GET /api/reco?top_k=24',
      'Backend lazily loads streaming data + outputs/data metadata, builds/caches track vectors',
      'Backend computes the preference vector, cosine scores, damps favourites, runs MMR, attributes features',
      'Frontend renders a responsive card grid: track / artist / album, score chip, why summary, feature chips',
      'User clicks a mood chip -> page re-fetches with target_mood and the card set changes',
      'User clicks Export CSV -> browser downloads recommendations.csv for the active mood',
    ],
    usage: [
      'Start the API: cd apps/api && venv/bin/uvicorn app.main:app --port 3011',
      'Start the web app: cd apps/web && npm run dev',
      'Navigate to Recommendations in the left nav (still marked experimental)',
      'Filter by Happy / Energetic / Chill, or leave on All',
      'Read why.summary and the feature chips on each card to see the rationale',
      'Click Export CSV to download the current list',
      'curl http://localhost:3011/api/reco?top_k=5&target_mood=chill for the raw JSON',
    ],
  },
  nextSteps: [
    'Implement Phase 7: Predictive Simulator (artist-level Markov chain by hour-of-day bucket)',
    'If real audio features become available again, swap the behavioural mood dims for true valence/energy/danceability',
    'Consider collaborative signals from data/other users/*.zip for a hybrid score',
    'Add an offline evaluation notebook (precision@k against held-out recent plays)',
  ],
  conclusion:
    'Phase 6 ships a working, explainable content-based recommender despite the loss of the Spotify audio-features API, by synthesising track vectors from listening behaviour and metadata. The feature model is an approximation and is labelled as such in the UI, but the endpoint shape, MMR diversification, and why.top_features attribution match the Phase 6 spec and give a solid base to swap in better features later.',
};

writePhaseDoc(phase6Params);
