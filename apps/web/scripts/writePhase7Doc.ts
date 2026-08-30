#!/usr/bin/env node
//
// Run with:  cd apps/web && npm run doc:phase7
//
// Writes the Phase 7 report to repo-root documentation/ via writePhaseDoc().

import { writePhaseDoc, PhaseDocParams } from './writePhaseDoc.ts';

const phase7Params: PhaseDocParams = {
  phaseNumber: 7,
  phaseName: 'Predictive Simulator',
  status: 'Completed',
  overview:
    'Added an artist-level Markov chain simulator. Consecutive plays within a listening session (30-minute gap threshold, reusing the Phase 5 session logic) define artist->artist transitions, optionally bucketed by hour-of-day. Given a seed artist and an hour, the backend runs a deterministic most-probable walk with additive (Laplace) smoothing over the observed successor set and returns the next N plays with their transition probabilities. The Simulator page provides a seed-artist autocomplete, an N slider (5-50), an hour-of-day selector, a run button, a probability-bar result list, and CSV export.',
  timeToComplete: '1.5 hours',
  filesCreated: [
    'apps/api/app/routes/sim.py - /api/simulate/next, /api/simulate/artists, /api/export/simulation endpoints',
    'apps/web/scripts/writePhase7Doc.ts - this documentation generator',
    'documentation/<timestamp>_phase_7_predictive_simulator.md - this document',
  ],
  filesModified: [
    'apps/api/app/services/data_loader.py - added SIM_* constants, _markov_model cache, _build_artist_transitions, get_sim_artists, get_simulation, get_simulation_csv_rows',
    'apps/api/app/main.py - registered sim router',
    'apps/web/src/types/api.ts - added SimulationStep and SimulationResponse types',
    'apps/web/src/api/client.ts - added getSimulation, getSimulationArtists, exportSimulation',
    'apps/web/src/pages/Simulator.tsx - full rewrite from stub to functional simulator UI',
    'apps/web/package.json - added doc:phase7 script',
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
      'Let the user explore "if I start with artist X at hour H, who am I likely to play next?" by walking a Markov chain learned from their own in-session listening transitions.',
    features: [
      'GET /api/simulate/next?n=&seed=&hour= returns a sequence of {step, from_artist, to_artist, probability}',
      'GET /api/simulate/artists returns the seed-autocomplete vocabulary (top 300 artists by play count)',
      'GET /api/export/simulation streams the same sequence as CSV',
      'Optional hour-of-day bucketing; per-artist rows fall back to the any-hour aggregate when an hour has no data for that artist',
      'Unknown seed is handled gracefully: seed_status="unknown" and the walk falls back to the default seed',
      'No seed given: seed_status="default", auto-seeded from the top artist for the chosen hour (or globally)',
      'Simulator page: autocomplete + N slider + hour select + Simulate button + probability-bar list + CSV export, with skeleton, empty, warning-chip and truncated states',
    ],
    implementation: [
      '_build_artist_transitions sorts music plays by timestamp, walks consecutive pairs, and only counts a transition when the inter-play gap is <= SIM_GAP_MINUTES (30), mirroring _build_sessions',
      'Transition counts are stored as nested defaultdicts: by_hour[hour][from][to] and an any-hour all[from][to]; also hour_plays[hour][artist] and global plays[artist] for default seeding',
      'The whole model is cached on self._markov_model (streaming data is immutable per process), so repeated simulations are cheap',
      'get_simulation clamps n to [1, SIM_MAX_N], validates hour to 0-23, resolves the seed case-insensitively against the vocabulary, then runs the walk',
      'At each step the successor distribution is Laplace-smoothed as (count + alpha) / (total + alpha * k); the most-probable successor is chosen deterministically',
      'The current artist is skipped when picking the next hop (unless it is the only successor) so the sequence stays exploratory rather than self-looping on the top artist; a forced self-loop sets truncated=true and stops',
      'Frontend loads the artist list once on mount; the simulation runs only on the Simulate button press (not on every control change); errors go through the zustand store to the global ErrorBanner',
      'CSV export reuses the anchor-download helper from Recommendations.tsx against the streaming backend endpoint',
    ],
    flow: [
      'User opens the Simulator page; the seed autocomplete populates from GET /api/simulate/artists',
      'User optionally picks a seed artist, sets N with the slider, and picks an hour of day',
      'User presses Simulate; frontend calls GET /api/simulate/next?n=&seed=&hour=',
      'Backend lazily loads streaming data, builds/caches the transition model, resolves the seed, and walks the chain',
      'Frontend renders the sequence as a list of #step from -> to rows, each with a determinate LinearProgress probability bar and a percentage',
      'Warning / info chips show when the seed was unknown or auto-seeded, when an hour filter is active, and when the chain ended early',
      'User clicks Export CSV to download simulation.csv (step, from_artist, to_artist, probability)',
    ],
    usage: [
      'Start the API: cd apps/api && venv/bin/uvicorn app.main:app --port 3011',
      'Start the web app: cd apps/web && npm run dev',
      'Navigate to Simulator in the left nav (marked experimental)',
      'Pick a seed artist or leave blank, set the number of plays, choose an hour or "Any hour"',
      'Press Simulate and read the probability bars down the sequence',
      'Click Export CSV to download the sequence',
      'curl "http://localhost:3011/api/simulate/next?n=10&seed=ABBA&hour=8" for the raw JSON',
    ],
  },
  nextSteps: [
    'Add an HMM over heuristic mood states on top of the artist chain (deferred from this phase)',
    'Add a stochastic sampling mode (weighted random walk) alongside the deterministic most-probable walk',
    'Visualise the transition graph (nodes = artists, edge weight = probability) instead of a flat list',
    'Build per-platform chains so mobile vs desktop transitions can be compared',
    'Expose a "temperature" control to sharpen or flatten the successor distribution',
  ],
  conclusion:
    'Phase 7 ships a working artist-level Markov simulator that reuses the existing session-gap logic and the Phase 6 route/loader/page patterns. The deterministic walk with Laplace smoothing and a self-loop guard keeps the output legible, the endpoint shape and CSV export match the spec, and the model cache keeps repeated runs fast. Stochastic sampling and an HMM mood layer are the natural follow-ups.',
};

writePhaseDoc(phase7Params);
