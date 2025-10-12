#!/usr/bin/env ts-node

import * as fs from 'fs';
import * as path from 'path';

interface PhaseDocParams {
  phaseNumber: number;
  phaseName: string;
  status: 'Completed' | 'Partial' | 'Blocked';
  overview: string;
  timeToComplete: string;
  filesCreated: string[];
  filesModified: string[];
  checklist: { [key: string]: boolean };
  implementation: {
    purpose: string;
    features: string[];
    implementation: string[];
    flow: string[];
    usage: string[];
  };
  nextSteps: string[];
  conclusion: string;
}

function generatePhaseDoc(params: PhaseDocParams): string {
  const now = new Date();
  const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0].replace('T', '_');
  const dateString = now.toISOString().replace('T', ' ').split('.')[0];

  const checklistItems = Object.entries(params.checklist)
    .map(([item, done]) => `- [${done ? 'x' : ' '}] ${item}`)
    .join('\n');

  const doc = `# ${params.phaseName} — Phase ${params.phaseNumber}
**Date:** ${dateString}
**Status:** ${params.status}
**Time to complete:** ${params.timeToComplete}

## Overview
${params.overview}

## Files Created
${params.filesCreated.map(f => `- ${f}`).join('\n')}

## Files Modified
${params.filesModified.map(f => `- ${f}`).join('\n')}

## Checklist
${checklistItems}

## What Was Implemented

### Purpose
${params.implementation.purpose}

### Features
${params.implementation.features.map(f => `- ${f}`).join('\n')}

### Implementation
${params.implementation.implementation.map(i => `- ${i}`).join('\n')}

### Flow
${params.implementation.flow.map(f => `- ${f}`).join('\n')}

### Usage
${params.implementation.usage.map(u => `- ${u}`).join('\n')}

## Next Steps
${params.nextSteps.map(s => `- ${s}`).join('\n')}

## Conclusion
${params.conclusion}
`;

  return doc;
}

function writePhaseDoc(params: PhaseDocParams): string {
  const now = new Date();
  const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0].replace('T', '_');

  const docDir = path.join(__dirname, '../../documentation');
  if (!fs.existsSync(docDir)) {
    fs.mkdirSync(docDir, { recursive: true });
  }

  const filename = `${timestamp}_phase_${params.phaseNumber}_${params.phaseName.toLowerCase().replace(/\s+/g, '_')}.md`;
  const filepath = path.join(docDir, filename);

  const content = generatePhaseDoc(params);
  fs.writeFileSync(filepath, content, 'utf-8');

  console.log(`✅ Phase ${params.phaseNumber} documentation written to: ${filename}`);
  return filepath;
}

// Export for use in other scripts
export { PhaseDocParams, writePhaseDoc, generatePhaseDoc };

// CLI usage
if (require.main === module) {
  // Example usage - can be customized per phase
  const exampleParams: PhaseDocParams = {
    phaseNumber: 0,
    phaseName: 'Foundations',
    status: 'Completed',
    overview: 'Set up project skeleton, Material-UI theme, navigation, and documentation tooling.',
    timeToComplete: '45 minutes',
    filesCreated: [
      'frontend/ - Vite + React + TypeScript project',
      'backend/ - FastAPI application',
      // Add more files here
    ],
    filesModified: [],
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
      purpose: 'Create the foundation for the Spotify Stats web application.',
      features: [
        'Vite + React + TypeScript frontend',
        'Material-UI with dark theme',
        'React Router v6 navigation',
        'FastAPI backend with health endpoint',
        'Documentation generation tooling',
      ],
      implementation: [
        'Initialized Vite project with React + TypeScript',
        'Installed Material-UI, React Router, Axios, Zustand',
        'Created theme provider with Spotify-themed dark mode',
        'Implemented responsive drawer navigation',
        'Set up 7 page components (Overview, Moods, Discovery, Milestones, Sessions, Recommendations, Simulator)',
        'Created FastAPI backend with CORS and health check',
        'Built documentation generation script',
      ],
      flow: [
        'User accesses the web app',
        'App loads with dark theme and drawer navigation',
        'User can navigate between all pages',
        'Backend health endpoint is accessible',
      ],
      usage: [
        'Frontend: `cd frontend && npm run dev`',
        'Backend: `cd backend && uvicorn app.main:app --reload`',
        'Generate docs: `npm run doc:phase`',
      ],
    },
    nextSteps: [
      'Implement Phase 1: Overview dashboard with stat cards and charts',
      'Connect frontend to backend API endpoints',
      'Load and display actual Spotify streaming data',
    ],
    conclusion: 'Phase 0 successfully establishes the foundation for the Spotify Stats application with a robust frontend and backend architecture.',
  };

  writePhaseDoc(exampleParams);
}
