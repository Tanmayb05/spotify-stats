import { useEffect, useMemo, useState } from 'react';

export type ChartRange = 'all' | '12m' | '6m' | '3m';

export interface UseTimeRange<T> {
  chartRange: ChartRange;
  sliderValue: number;
  setSliderValue: (v: number) => void;
  handleRangeChange: (r: ChartRange) => void;
  rangeMonths: number;
  maxSliderValue: number;
  filtered: T[];
}

/**
 * The Chip + Slider month-window control shared by the Insights "Monthly
 * Listening Trends" and "Discovery Timeline" sections. Extracted from the
 * byte-identical copies that were in Overview.tsx and Discovery.tsx.
 *
 * Fixes a latent bug in both originals: sliderValue was never re-clamped when
 * `data` changed length (a user switch shrinks the series -> the slider points
 * past the end and the chart renders empty).
 */
export function useTimeRange<T>(data: T[]): UseTimeRange<T> {
  const [chartRange, setChartRange] = useState<ChartRange>('all');
  const [sliderValue, setSliderValue] = useState(0);

  const rangeMonths = chartRange === 'all' ? data.length : parseInt(chartRange, 10);
  const maxSliderValue = Math.max(0, data.length - rangeMonths);

  useEffect(() => {
    setSliderValue((v) => Math.min(v, maxSliderValue));
  }, [maxSliderValue]);

  const handleRangeChange = (newRange: ChartRange) => {
    setChartRange(newRange);
    if (newRange === 'all') {
      setSliderValue(0);
    } else {
      const months = parseInt(newRange, 10);
      setSliderValue(Math.max(0, data.length - months));
    }
  };

  const filtered = useMemo(
    () =>
      chartRange === 'all'
        ? data
        : data.slice(sliderValue, sliderValue + rangeMonths),
    [data, chartRange, sliderValue, rangeMonths]
  );

  return {
    chartRange,
    sliderValue,
    setSliderValue,
    handleRangeChange,
    rangeMonths,
    maxSliderValue,
    filtered,
  };
}
