import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Skeleton,
  Grid,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  alpha,
} from '@mui/material';
import { Groups } from '@mui/icons-material';
import { BarChart } from '@mui/x-charts/BarChart';
import DataTable, { type Column } from '../components/DataTable';
import { api } from '../api/client';
import { useAppStore } from '../store/app';
import { formatNumber } from '../utils/format';
import type {
  CompareUser,
  LeaderboardRow,
  OverlapResult,
  SimilarityMatrix,
  TopArtistsMulti,
} from '../types/api';

const SERIES_COLORS = ['#2dd881', '#4ea699', '#6fedb7', '#140d4f', '#a54092', '#e5bbdd'];
const HEAT_COLOR = '#2dd881';

const leaderboardColumns: Column<LeaderboardRow>[] = [
  { key: 'display_name', label: 'User' },
  { key: 'total_streams', label: 'Streams', align: 'right', format: (v) => formatNumber(v) },
  { key: 'total_hours', label: 'Hours', align: 'right', format: (v) => formatNumber(Math.round(v)) },
  { key: 'unique_artists', label: 'Artists', align: 'right', format: (v) => formatNumber(v) },
  { key: 'unique_tracks', label: 'Tracks', align: 'right', format: (v) => formatNumber(v) },
  { key: 'skip_rate', label: 'Skip %', align: 'right', format: (v) => `${v.toFixed(1)}%` },
  { key: 'first_stream', label: 'From', align: 'right' },
  { key: 'last_stream', label: 'To', align: 'right' },
];

const panelSx = {
  p: 5,
  transition: 'all 0.3s ease-in-out',
  '&:hover': { boxShadow: '0 8px 16px rgba(0, 0, 0, 0.12)' },
} as const;

export default function Comparison() {
  const { setError } = useAppStore();

  const [users, setUsers] = useState<CompareUser[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [matrix, setMatrix] = useState<SimilarityMatrix | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [overlap, setOverlap] = useState<OverlapResult | null>(null);
  const [topArtists, setTopArtists] = useState<TopArtistsMulti>({});

  const [baseLoading, setBaseLoading] = useState(true);
  const [panelLoading, setPanelLoading] = useState(false);

  // Initial load: users + leaderboard + matrix. Default selection = primary + top 2.
  useEffect(() => {
    (async () => {
      try {
        setBaseLoading(true);
        setError(null);
        const [u, lb, mx] = await Promise.all([
          api.getCompareUsers(),
          api.getLeaderboard(),
          api.getSimilarityMatrix(),
        ]);
        setUsers(u);
        setLeaderboard(lb);
        setMatrix(mx);

        const primary = u.find((x) => x.is_primary)?.user_id;
        const byStreams = lb
          .filter((r) => !r.is_primary)
          .map((r) => r.user_id);
        const defaults = [primary, byStreams[0], byStreams[1]].filter(
          (x): x is string => Boolean(x)
        );
        setSelected(defaults);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load comparison data');
      } finally {
        setBaseLoading(false);
      }
    })();
  }, [setError]);

  // Selection-dependent panels: overlap + top-artist compare.
  useEffect(() => {
    if (selected.length === 0) return;
    (async () => {
      try {
        setPanelLoading(true);
        const [ov, ta] = await Promise.all([
          selected.length >= 2
            ? api.getOverlap(selected)
            : Promise.resolve(null),
          api.getTopArtistsMulti(selected, 10),
        ]);
        setOverlap(ov);
        setTopArtists(ta);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load comparison panels');
      } finally {
        setPanelLoading(false);
      }
    })();
  }, [selected, setError]);

  const toggleUser = (id: string) => {
    setSelected((cur) => {
      if (cur.includes(id)) {
        if (cur.length <= 1) return cur; // keep at least 1
        return cur.filter((x) => x !== id);
      }
      if (cur.length >= 6) return cur; // cap at 6
      return [...cur, id];
    });
  };

  const nameOf = useMemo(() => {
    const m = new Map(users.map((u) => [u.user_id, u.is_primary ? 'You' : u.display_name]));
    return (id: string) => m.get(id) ?? id;
  }, [users]);

  const matrixMax = useMemo(() => {
    if (!matrix) return 1;
    let mx = 0;
    for (const row of matrix.matrix)
      for (const v of row) if (v != null && v > mx) mx = v;
    return mx || 1;
  }, [matrix]);

  const topArtistNames = Object.keys(topArtists);

  return (
    <Box sx={{ pb: 4 }}>
      <Typography variant="h3" gutterBottom fontWeight={700} sx={{ mb: 2 }}>
        <Groups sx={{ fontSize: 36, mr: 1, verticalAlign: 'text-bottom' }} />
        Comparison
      </Typography>
      <Typography
        variant="body1"
        color="text.secondary"
        paragraph
        sx={{ mb: 5, fontSize: '1.1rem' }}
      >
        How your listening stacks up against {users.length > 0 ? users.length - 1 : 9} friends.
      </Typography>

      {/* User selection chips */}
      <Paper sx={{ ...panelSx, p: 3, mb: 4 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
          Compare (pick 2–6) — used by the overlap and top-artist panels
        </Typography>
        {baseLoading ? (
          <Skeleton variant="rectangular" height={40} />
        ) : (
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
            {users.map((u) => {
              const on = selected.includes(u.user_id);
              return (
                <Chip
                  key={u.user_id}
                  label={u.is_primary ? 'You' : u.display_name}
                  color={on ? 'primary' : 'default'}
                  variant={on ? 'filled' : 'outlined'}
                  onClick={() => toggleUser(u.user_id)}
                  sx={{ cursor: 'pointer' }}
                />
              );
            })}
          </Stack>
        )}
      </Paper>

      <Grid container spacing={{ xs: 3, lg: 5 }} direction="column">
        {/* Panel 1 — Leaderboard */}
        <Grid size={12}>
          <Paper sx={panelSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
              Leaderboard
            </Typography>
            {baseLoading ? (
              <Skeleton variant="rectangular" height={480} />
            ) : (
              <>
                <Box sx={{ width: '100%', overflowX: 'auto', mb: 4 }}>
                  <BarChart
                    yAxis={[
                      {
                        data: leaderboard.map((r) => (r.is_primary ? 'You' : r.display_name)),
                        scaleType: 'band',
                      },
                    ]}
                    series={[
                      {
                        data: leaderboard.map((r) => r.total_streams),
                        label: 'Total streams',
                        color: HEAT_COLOR,
                      },
                    ]}
                    layout="horizontal"
                    height={480}
                    margin={{ left: 110, right: 40, top: 40, bottom: 60 }}
                    sx={{
                      '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': { fontSize: '0.875rem' },
                    }}
                  />
                </Box>
                <DataTable
                  columns={leaderboardColumns}
                  data={leaderboard}
                  aria-label="Per-user listening leaderboard"
                />
              </>
            )}
          </Paper>
        </Grid>

        {/* Panel 2 — Shared-artist overlap */}
        <Grid size={12}>
          <Paper sx={panelSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
              Shared-artist overlap
            </Typography>
            {selected.length < 2 ? (
              <Typography color="text.secondary">Select at least 2 users above.</Typography>
            ) : panelLoading || !overlap ? (
              <Skeleton variant="rectangular" height={360} />
            ) : (
              <Grid container spacing={4}>
                <Grid size={{ xs: 12, md: 7 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                    Pairwise similarity
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Pair</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>Shared</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>Only A</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>Only B</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 700 }}>Jaccard %</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {overlap.pairs.map((p, i) => (
                          <TableRow key={i} hover>
                            <TableCell>{p.user_a} ↔ {p.user_b}</TableCell>
                            <TableCell align="right">{formatNumber(p.shared)}</TableCell>
                            <TableCell align="right">{formatNumber(p.only_a)}</TableCell>
                            <TableCell align="right">{formatNumber(p.only_b)}</TableCell>
                            <TableCell align="right">{p.jaccard.toFixed(1)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Grid>
                <Grid size={{ xs: 12, md: 5 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                    Top artists shared by all {overlap.users.length} ({formatNumber(overlap.shared_by_all_count)} total)
                  </Typography>
                  <Stack spacing={0.5}>
                    {overlap.top_shared_by_all.slice(0, 15).map((a) => (
                      <Box
                        key={a.artist}
                        sx={{ display: 'flex', justifyContent: 'space-between' }}
                      >
                        <Typography variant="body2">{a.artist}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {formatNumber(a.total_plays)}
                        </Typography>
                      </Box>
                    ))}
                    {overlap.top_shared_by_all.length === 0 && (
                      <Typography variant="body2" color="text.secondary">
                        No artist is common to every selected user.
                      </Typography>
                    )}
                  </Stack>
                </Grid>
              </Grid>
            )}
          </Paper>
        </Grid>

        {/* Panel 3 — Similarity matrix */}
        <Grid size={12}>
          <Paper sx={panelSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
              Taste-similarity matrix
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Pairwise artist Jaccard %. Darker = more shared taste.
            </Typography>
            {baseLoading || !matrix ? (
              <Skeleton variant="rectangular" height={420} />
            ) : (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <Table
                  size="small"
                  sx={{ minWidth: 640, '& td, & th': { textAlign: 'center', px: 1 } }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell />
                      {matrix.users.map((u) => (
                        <TableCell key={u} sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                          {u}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {matrix.matrix.map((row, i) => (
                      <TableRow key={matrix.users[i]}>
                        <TableCell sx={{ fontWeight: 700, fontSize: '0.8rem' }}>
                          {matrix.users[i]}
                        </TableCell>
                        {row.map((v, j) => (
                          <TableCell
                            key={j}
                            sx={{
                              bgcolor:
                                v == null
                                  ? 'action.hover'
                                  : alpha(HEAT_COLOR, Math.min(v / matrixMax, 1)),
                              fontSize: '0.8rem',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {v == null ? '—' : v.toFixed(0)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Panel 4 — Top-artist compare */}
        <Grid size={12}>
          <Paper sx={panelSx}>
            <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
              Top artists — side by side
            </Typography>
            {selected.length === 0 ? (
              <Typography color="text.secondary">Select at least 1 user above.</Typography>
            ) : panelLoading ? (
              <Skeleton variant="rectangular" height={420} />
            ) : (
              <Grid container spacing={3}>
                {topArtistNames.map((name, idx) => {
                  const rows = topArtists[name] ?? [];
                  return (
                    <Grid size={{ xs: 12, md: 6 }} key={name}>
                      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
                        {name}
                      </Typography>
                      <Box sx={{ width: '100%', overflowX: 'auto' }}>
                        <BarChart
                          yAxis={[{ data: rows.map((r) => r.artist), scaleType: 'band' }]}
                          series={[
                            {
                              data: rows.map((r) => r.streams),
                              label: 'Streams',
                              color: SERIES_COLORS[idx % SERIES_COLORS.length],
                            },
                          ]}
                          layout="horizontal"
                          height={420}
                          margin={{ left: 160, right: 24, top: 30, bottom: 50 }}
                          sx={{
                            '.MuiChartsAxis-left .MuiChartsAxis-tickLabel': {
                              fontSize: '0.8rem',
                            },
                          }}
                        />
                      </Box>
                    </Grid>
                  );
                })}
              </Grid>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
