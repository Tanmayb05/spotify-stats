/**
 * Format a number with thousand separators
 * Example: 12345 -> "12,345"
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

/**
 * Format hours to a human-readable string
 * Example: 125.5 -> "125.5 hours" or "125h 30m"
 */
export function formatHours(hours: number, detailed = false): string {
  if (detailed) {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  return `${hours.toFixed(1)} hours`;
}

/**
 * Format minutes to hours and minutes
 * Example: 125 -> "2h 5m"
 */
export function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);

  if (hours === 0) {
    return `${mins}m`;
  }
  if (mins === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${mins}m`;
}

/**
 * Format a date to a readable string
 * Example: "2024-01-15" -> "Jan 15, 2024"
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(d);
}

/**
 * Format a percentage
 * Example: 0.1234 -> "12.3%"
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format large numbers with K, M, B suffixes
 * Example: 12345 -> "12.3K"
 */
export function formatCompact(num: number): string {
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1)}B`;
  }
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  return num.toString();
}

/**
 * Truncate text with ellipsis
 * Example: "Very long text here" -> "Very long te..."
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}
