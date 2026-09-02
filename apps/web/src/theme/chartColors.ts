/**
 * The project chart palette (CLAUDE.md). Hoisted out of the inline hex literals
 * that were scattered across Overview / ListeningPatterns / Discovery.
 */
export const CHART = {
  emerald: '#2dd881', // primary accent
  keppel: '#4ea699', // secondary
  aquamarine: '#6fedb7', // tertiary
  federalBlue: '#140d4f',
  darkPurple: '#1c0b19',
} as const;

/** Status colors for the Data Health check chips. */
export const STATUS_COLOR = {
  pass: '#2dd881',
  warn: '#6fedb7',
  fail: '#ef5350', // theme error.main
  skip: '#9e9e9e',
} as const;
