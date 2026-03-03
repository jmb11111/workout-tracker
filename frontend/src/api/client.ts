import type {
  WorkoutDay,
  CalendarResponse,
  WorkoutLog,
  WorkoutLogCreate,
  WorkoutLogUpdate,
  ExerciseResult,
  ExerciseResultCreate,
  ConditioningResult,
  ConditioningResultCreate,
  Movement,
  MovementHistoryResponse,
  MovementStatsResponse,
  GroupedPersonalRecords,
  BenchmarkGroup,
  User,
  UserUpdate,
  LoginUrlResponse,
  TokenResponse,
  ScraperStatusResponse,
  ScraperTriggerResponse,
  ReparseResponse,
} from '../types';

// ---------------------------------------------------------------------------
// Base fetch wrapper
// ---------------------------------------------------------------------------

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

function getToken(): string | null {
  return localStorage.getItem('access_token');
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `API error: ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // ignore parse error
    }
    throw new ApiError(message, response.status);
  }

  // Handle 204 No Content or null responses
  const text = await response.text();
  if (!text || text === 'null') {
    return null as T;
  }
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Workouts
// ---------------------------------------------------------------------------

export async function getToday(): Promise<WorkoutDay> {
  return apiFetch<WorkoutDay>('/api/workouts/today');
}

export async function getWorkout(date: string): Promise<WorkoutDay> {
  return apiFetch<WorkoutDay>(`/api/workouts/${date}`);
}

export async function getCalendar(
  year: number,
  month: number,
): Promise<CalendarResponse> {
  return apiFetch<CalendarResponse>(`/api/workouts/calendar/${year}/${month}`);
}

// ---------------------------------------------------------------------------
// Results / Logs
// ---------------------------------------------------------------------------

export async function createLog(
  data: WorkoutLogCreate,
): Promise<WorkoutLog> {
  return apiFetch<WorkoutLog>('/api/results/log', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getLog(
  workoutDayId: number,
): Promise<WorkoutLog | null> {
  return apiFetch<WorkoutLog | null>(`/api/results/log/${workoutDayId}`);
}

export async function updateLog(
  logId: number,
  data: WorkoutLogUpdate,
): Promise<WorkoutLog> {
  return apiFetch<WorkoutLog>(`/api/results/log/${logId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function saveExerciseResults(
  logId: number,
  results: ExerciseResultCreate[],
): Promise<ExerciseResult[]> {
  return apiFetch<ExerciseResult[]>(`/api/results/log/${logId}/exercises`, {
    method: 'POST',
    body: JSON.stringify(results),
  });
}

export async function saveConditioningResults(
  logId: number,
  results: ConditioningResultCreate[],
): Promise<ConditioningResult[]> {
  return apiFetch<ConditioningResult[]>(
    `/api/results/log/${logId}/conditioning`,
    {
      method: 'POST',
      body: JSON.stringify(results),
    },
  );
}

// ---------------------------------------------------------------------------
// Movements
// ---------------------------------------------------------------------------

export async function getMovements(params?: {
  q?: string;
  movement_type?: string;
  muscle_group?: string;
}): Promise<Movement[]> {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set('q', params.q);
  if (params?.movement_type) searchParams.set('movement_type', params.movement_type);
  if (params?.muscle_group) searchParams.set('muscle_group', params.muscle_group);
  const qs = searchParams.toString();
  return apiFetch<Movement[]>(`/api/movements/${qs ? '?' + qs : ''}`);
}

export async function getMovementHistory(
  id: number,
  page = 1,
  pageSize = 20,
): Promise<MovementHistoryResponse> {
  return apiFetch<MovementHistoryResponse>(
    `/api/movements/${id}/history?page=${page}&page_size=${pageSize}`,
  );
}

export async function getMovementStats(
  id: number,
): Promise<MovementStatsResponse> {
  return apiFetch<MovementStatsResponse>(`/api/movements/${id}/stats`);
}

// ---------------------------------------------------------------------------
// Records
// ---------------------------------------------------------------------------

export async function getRecords(params?: {
  movement_type?: string;
  muscle_group?: string;
}): Promise<GroupedPersonalRecords[]> {
  const searchParams = new URLSearchParams();
  if (params?.movement_type) searchParams.set('movement_type', params.movement_type);
  if (params?.muscle_group) searchParams.set('muscle_group', params.muscle_group);
  const qs = searchParams.toString();
  return apiFetch<GroupedPersonalRecords[]>(`/api/records/${qs ? '?' + qs : ''}`);
}

export async function getBenchmarks(): Promise<BenchmarkGroup[]> {
  return apiFetch<BenchmarkGroup[]>('/api/records/benchmarks');
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export async function getMe(): Promise<User> {
  return apiFetch<User>('/api/users/me');
}

export async function updateMe(data: UserUpdate): Promise<User> {
  return apiFetch<User>('/api/users/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function getLoginUrl(): Promise<LoginUrlResponse> {
  return apiFetch<LoginUrlResponse>('/api/auth/login');
}

export async function handleCallback(code: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>(`/api/auth/callback?code=${encodeURIComponent(code)}`);
}

export async function refreshToken(token: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>(
    `/api/auth/refresh?refresh_token=${encodeURIComponent(token)}`,
    { method: 'POST' },
  );
}

// ---------------------------------------------------------------------------
// Scraper
// ---------------------------------------------------------------------------

export async function triggerScrape(
  date?: string,
): Promise<ScraperTriggerResponse> {
  const qs = date ? `?target_date=${date}` : '';
  return apiFetch<ScraperTriggerResponse>(`/api/scraper/trigger${qs}`, {
    method: 'POST',
  });
}

export async function reparseWorkout(
  workoutDayId: number,
): Promise<ReparseResponse> {
  return apiFetch<ReparseResponse>(`/api/scraper/reparse/${workoutDayId}`, {
    method: 'POST',
  });
}

export async function getScraperStatus(): Promise<ScraperStatusResponse> {
  return apiFetch<ScraperStatusResponse>('/api/scraper/status');
}

// Re-export error class
export { ApiError };
