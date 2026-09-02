import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
  Chip,
  Tabs,
  Tab,
  Alert,
} from '@mui/material';
import { CheckCircle, Warning, Error as ErrorIcon } from '@mui/icons-material';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import StatCard from '../components/StatCard';
import DataTable from '../components/DataTable';
import type { Column } from '../components/DataTable';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatNumber, formatDate, formatPercent } from '../utils/format';
import { CHART, STATUS_COLOR } from '../theme/chartColors';
import type {
  DataHealthResponse,
  DqCheck,
  PerUserHealth,
} from '../types/api';

const paperSx = {
  p: 5,
  transition: 'all 0.3s ease-in-out',
  '&:hover': { boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)' },
} as const;

const tabSx = { textTransform: 'none', fontWeight: 600, fontSize: '1rem' } as const;

function statusOf(c: DqCheck): 'PASS' | 'WARN' | 'FAIL' | 'SKIP' {
  if (c.skipped) return 'SKIP';
  if (c.passed) return 'PASS';
  return c.severity === 'blocking' ? 'FAIL' : 'WARN';
}

export default function DataHealth() {
  const { setError, selectedUserId } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DataHealthResponse | null>(null);
  const [catTab, setCatTab] = useState(0);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await api.getDataHealth());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data health');
    } finally {
      setLoading(false);
    }
  }, [setError]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUserId]);

  if (loading) {
    return (
      <Box sx={{ pb: 4 }}>
        <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>Data Health</Typography>
        <Skeleton variant="rectangular" height={140} sx={{ mb: 4 }} />
        <Skeleton variant="rectangular" height={550} />
      </Box>
    );
  }

  const dq = data?.dq;
  const ing = data?.ingest;
  const bothMissing = !dq?.has_run && !ing?.has_run;

  const cats = dq?.categories ?? [];
  const activeCat = cats[catTab];

  const checkColumns: Column<DqCheck & { _status: string }>[] = [
    { key: 'name', label: 'Check', align: 'left', width: '22%' },
    { key: 'severity', label: 'Severity', align: 'left' },
    { key: '_status', label: 'Status', align: 'left', format: (v) => v },
    { key: 'observed', label: 'Observed', align: 'left' },
    { key: 'expected', label: 'Expected', align: 'left' },
    { key: 'rows_failed', label: 'Rows Failed', align: 'right', format: (v) => formatNumber(v) },
  ];

  const perUserColumns: Column<PerUserHealth & { _status: string }>[] = [
    { key: 'username', label: 'User', align: 'left' },
    { key: 'rows_silver', label: 'Rows (silver)', align: 'right', format: (v) => formatNumber(v) },
    { key: 'dups_dropped', label: 'Dups Dropped', align: 'right', format: (v) => formatNumber(v) },
    { key: 'rows_quarantined', label: 'Quarantined', align: 'right', format: (v) => formatNumber(v) },
    { key: 'max_ts', label: 'Last Play', align: 'left', format: (v) => (v ? formatDate(v) : '—') },
    { key: 'freshness_days', label: 'Days Stale', align: 'right', format: (v) => (v == null ? '—' : formatNumber(v)) },
    { key: '_status', label: 'Status', align: 'left', format: (v) => v },
  ];

  const funnelRows = ing?.has_run
    ? [
        { label: 'Raw', value: ing.rows_raw ?? 0 },
        { label: 'Valid', value: ing.rows_valid ?? 0 },
        { label: 'Landed', value: ing.rows_landed ?? 0 },
        { label: 'Silver', value: ing.rows_silver ?? 0 },
        { label: 'Fact', value: ing.rows_fact ?? 0 },
        { label: 'Quarantined', value: ing.rows_quarantined ?? 0 },
        { label: 'Dups Dropped', value: ing.dups_dropped ?? 0 },
      ]
    : [];

  const lastRunLabel = ing?.status ?? 'unknown';
  const lastRunIcon =
    lastRunLabel === 'success'
      ? <CheckCircle sx={{ color: CHART.emerald, fontSize: 28 }} />
      : lastRunLabel === 'partial'
      ? <Warning sx={{ color: CHART.aquamarine, fontSize: 28 }} />
      : <ErrorIcon sx={{ color: STATUS_COLOR.fail, fontSize: 28 }} />;

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>Data Health</Typography>
      <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 6, fontSize: '1.1rem' }}>
        Pipeline status, data-quality checks, and per-user freshness. Backend: <strong>{data?.backend}</strong>.
      </Typography>

      {bothMissing && (
        <Paper sx={{ ...paperSx, mb: 4 }}>
          <Alert severity="info">
            {dq?.message ??
              'No pipeline or DQ run recorded on this backend. The data-quality suite runs against the local Postgres pipeline (Dagster `data_quality` asset).'}
          </Alert>
        </Paper>
      )}

      {/* §1 Pipeline status */}
      {ing?.has_run && (
        <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 6 }}>
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
            <StatCard title="Last Run Status" value={lastRunLabel} subtitle={ing.finished_at ? formatDate(ing.finished_at) : undefined} icon={lastRunIcon} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
            <StatCard title="Rows in Fact Table" value={formatNumber(ing.rows_fact ?? 0)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
            <StatCard title="Users Ingested" value={formatNumber(ing.users ?? 0)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
            <StatCard title="Rows Quarantined" value={formatNumber(ing.rows_quarantined ?? 0)} />
          </Grid>
          {dq?.has_run && (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} sx={{ display: 'flex' }}>
              <StatCard
                title="DQ Checks Passed"
                value={`${dq.passed ?? 0} / ${dq.checks_total ?? 0}`}
                subtitle={`status: ${dq.status}`}
              />
            </Grid>
          )}
        </Grid>
      )}

      <Grid container spacing={{ xs: 3, lg: 5 }} direction="column">
        {/* §2 Ingestion funnel */}
        {ing?.has_run && (
          <Grid size={12}>
            <Paper sx={paperSx}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 4 }}>Ingestion Funnel</Typography>
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <BarChart
                  yAxis={[{ data: funnelRows.map((r) => r.label), scaleType: 'band' }]}
                  series={[{ data: funnelRows.map((r) => r.value), label: 'Rows', color: CHART.emerald }]}
                  layout="horizontal"
                  height={550}
                  margin={{ left: 150, right: 40, top: 40, bottom: 60 }}
                  sx={{ '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' } }}
                />
              </Box>
              {ing.invariants && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
                  {Object.entries(ing.invariants).map(([k, v]) => (
                    <Chip
                      key={k}
                      label={`${k.replace(/_/g, ' ')} ${v === null ? 'n/a' : v ? '✓' : '✗'}`}
                      size="small"
                      sx={{
                        bgcolor: v === null ? STATUS_COLOR.skip : v ? STATUS_COLOR.pass : STATUS_COLOR.fail,
                        color: '#0c050a',
                        fontWeight: 600,
                      }}
                    />
                  ))}
                </Box>
              )}
            </Paper>
          </Grid>
        )}

        {/* §3 Match rates */}
        {ing?.has_run && (
          <Grid size={12}>
            <Paper sx={paperSx}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 4 }}>Enrichment Match Rates</Typography>
              <Grid container spacing={{ xs: 2, md: 3 }} sx={{ mb: 3 }}>
                <Grid size={{ xs: 12, sm: 6 }} sx={{ display: 'flex' }}>
                  <StatCard
                    title="Track Match Rate"
                    value={ing.track_match_rate != null ? formatPercent(ing.track_match_rate) : '—'}
                    subtitle={ing.unmatched_tracks != null ? `${formatNumber(ing.unmatched_tracks)} unmatched tracks` : undefined}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }} sx={{ display: 'flex' }}>
                  <StatCard
                    title="Artist Match Rate"
                    value={ing.artist_match_rate != null ? formatPercent(ing.artist_match_rate) : '—'}
                    subtitle={ing.unmatched_artists != null ? `${formatNumber(ing.unmatched_artists)} unmatched artists` : undefined}
                  />
                </Grid>
              </Grid>
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <BarChart
                  yAxis={[{ data: ['Track', 'Artist'], scaleType: 'band' }]}
                  series={[{
                    data: [(ing.track_match_rate ?? 0) * 100, (ing.artist_match_rate ?? 0) * 100],
                    label: 'Match rate (%)',
                    color: CHART.keppel,
                    valueFormatter: (v) => `${v?.toFixed(1)}%`,
                  }]}
                  layout="horizontal"
                  height={300}
                  margin={{ left: 100, right: 40, top: 40, bottom: 60 }}
                />
              </Box>
            </Paper>
          </Grid>
        )}

        {/* §4 DQ checks */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Data-Quality Checks</Typography>
            {!dq?.has_run ? (
              <Alert severity="info">{dq?.message ?? 'No DQ run recorded.'}</Alert>
            ) : (
              <>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                  {cats.map((c) => (
                    <Chip
                      key={c.category}
                      label={`${c.category} ${c.passed}/${c.total}`}
                      size="small"
                      sx={{
                        bgcolor:
                          c.status === 'pass'
                            ? STATUS_COLOR.pass
                            : c.status === 'warn'
                            ? STATUS_COLOR.warn
                            : STATUS_COLOR.fail,
                        color: '#0c050a',
                        fontWeight: 700,
                        textTransform: 'capitalize',
                      }}
                    />
                  ))}
                </Box>
                <Tabs
                  value={catTab}
                  onChange={(_, v) => setCatTab(v)}
                  variant="scrollable"
                  scrollButtons="auto"
                  sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}
                >
                  {cats.map((c) => (
                    <Tab
                      key={c.category}
                      label={`${c.category} (${c.passed}/${c.total})`}
                      sx={{ ...tabSx, textTransform: 'capitalize' }}
                    />
                  ))}
                </Tabs>
                {activeCat && (
                  <DataTable
                    columns={checkColumns}
                    data={activeCat.checks.map((c) => ({ ...c, _status: statusOf(c) }))}
                    aria-label="Data quality checks"
                  />
                )}
              </>
            )}
          </Paper>
        </Grid>

        {/* §5 Per-user freshness */}
        {data && data.per_user.length > 0 && (
          <Grid size={12}>
            <Paper sx={paperSx}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Per-User Freshness</Typography>
              <DataTable
                columns={perUserColumns}
                data={data.per_user.map((u) => ({
                  ...u,
                  _status: u.freshness_status,
                }))}
                aria-label="Per-user data freshness"
              />
            </Paper>
          </Grid>
        )}

        {/* §6 Row-count trend */}
        {data && data.trend.length > 1 && (
          <Grid size={12}>
            <Paper sx={paperSx}>
              <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Row-Count Trend</Typography>
              <LineChart
                xAxis={[{
                  data: data.trend.map((_, i) => i),
                  scaleType: 'point',
                  valueFormatter: (v) => (data.trend[v]?.started_at ? formatDate(data.trend[v].started_at!) : ''),
                }]}
                series={[
                  { data: data.trend.map((t) => t.rows_fact), label: 'Rows (fact)', color: CHART.emerald, curve: 'catmullRom' },
                  { data: data.trend.map((t) => t.rows_quarantined), label: 'Quarantined', color: CHART.keppel, curve: 'catmullRom' },
                ]}
                height={600}
              />
            </Paper>
          </Grid>
        )}

        {/* §7 Quarantine */}
        <Grid size={12}>
          <Paper sx={paperSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>Quarantine</Typography>
            {data && data.quarantine.total > 0 ? (
              <>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                  {Object.entries(data.quarantine.by_rule).map(([rule, n]) => (
                    <Chip key={rule} label={`${rule}: ${n}`} size="small" color="warning" />
                  ))}
                </Box>
                <DataTable
                  columns={[
                    { key: 'rule', label: 'Rule', align: 'left' },
                    { key: 'source_file', label: 'Source File', align: 'left' },
                    { key: 'quarantined_at', label: 'When', align: 'left', format: (v) => (v ? formatDate(String(v)) : '—') },
                  ]}
                  data={data.quarantine.sample}
                  aria-label="Quarantined rows sample"
                />
              </>
            ) : (
              <Typography color="text.secondary">No rows quarantined in the latest run.</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
