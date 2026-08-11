"""SessionRepository — data access for sessions table."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCursorError
from app.core.pagination import decode_cursor, encode_cursor
from app.db.models.session import Session

_SESSION_CURSOR_NAMESPACE = "sessions"


@dataclass(frozen=True)
class IndexedSessionCreateRequest:
    """Redis write request for a user-indexed auth session."""

    user_id: str
    session_id: str
    session_json: str
    created_at: float
    max_sessions: int
    ttl_seconds: int


@dataclass(frozen=True)
class IndexedSessionCreateResult:
    """Atomic session creation metadata."""

    sequence: int
    live_indexed_sessions: int
    evicted_sessions: int


@dataclass(frozen=True)
class IndexedSessionDeleteResult:
    """Atomic session deletion metadata."""

    actor_identity: str | None
    user_id: str | None
    session_deleted: bool
    index_empty: bool


@dataclass(frozen=True)
class IndexedSessionRefreshRequest:
    """Atomic refresh request for an existing indexed session."""

    session_id: str
    now: float
    ttl_seconds: int
    expected_session_json: str | None = None
    replacement_session_json: str | None = None


_SESSION_SCORE_SCALE = 1_000_000


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _user_index_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


def _user_sequence_key(user_id: str) -> str:
    return f"user_sessions_seq:{user_id}"


_CREATE_INDEXED_SESSION_LUA = f"""
local session_type = redis.call('TYPE', KEYS[1]).ok
local index_type = redis.call('TYPE', KEYS[2]).ok
local sequence_type = redis.call('TYPE', KEYS[3]).ok
if session_type ~= 'none' and session_type ~= 'string' then
  return redis.error_reply('invalid-session-key-type')
end
if index_type ~= 'none' and index_type ~= 'zset' then
  return redis.error_reply('invalid-index-key-type')
end
if sequence_type ~= 'none' and sequence_type ~= 'string' then
  return redis.error_reply('invalid-sequence-key-type')
end

local created_at = tonumber(ARGV[3])
local max_sessions = tonumber(ARGV[4])
local ttl_seconds = tonumber(ARGV[5])
if created_at == nil then
  return redis.error_reply('invalid-created-at')
end
if max_sessions == nil then
  return redis.error_reply('invalid-max-sessions')
end
if ttl_seconds == nil or ttl_seconds <= 0 then
  return redis.error_reply('invalid-session-ttl')
end
local requested_payload = cjson.decode(ARGV[2])
if type(requested_payload['user_id']) ~= 'string' or requested_payload['user_id'] ~= ARGV[6] then
  return redis.error_reply('invalid-session-user')
end

local existing_raw = redis.call('GET', KEYS[1])
if existing_raw ~= false then
  local existing_payload = cjson.decode(existing_raw)
  if type(existing_payload['user_id']) == 'string' and existing_payload['user_id'] ~= ARGV[6] then
    return redis.error_reply('session-user-mismatch')
  end
end

local sequence_raw = redis.call('GET', KEYS[3])
if sequence_raw ~= false and string.match(sequence_raw, '^%d+$') == nil then
  return redis.error_reply('invalid-sequence-value')
end

local function sequence_from_score(score)
  if score == nil then
    return 0
  end
  local scaled = tonumber(score)
  if scaled == nil or scaled < {_SESSION_SCORE_SCALE} then
    return 0
  end
  local sequence = scaled - (math.floor(scaled / {_SESSION_SCORE_SCALE}) * {_SESSION_SCORE_SCALE})
  if sequence < 0 then
    return 0
  end
  return math.floor(sequence)
end

if sequence_raw == false and redis.call('ZCARD', KEYS[2]) > 0 then
  local highest_scores = redis.call('ZREVRANGE', KEYS[2], 0, 0, 'WITHSCORES')
  local recovered_sequence = sequence_from_score(highest_scores[2])
  if recovered_sequence < redis.call('ZCARD', KEYS[2]) then
    recovered_sequence = redis.call('ZCARD', KEYS[2])
  end
  redis.call('SET', KEYS[3], recovered_sequence)
  sequence_raw = tostring(recovered_sequence)
end

local stale_members = redis.call('ZRANGE', KEYS[2], 0, -1)
for _, member in ipairs(stale_members) do
  if redis.call('EXISTS', 'session:' .. member) == 0 then
    redis.call('ZREM', KEYS[2], member)
  end
end

local existing_score = redis.call('ZSCORE', KEYS[2], ARGV[1])
local sequence
if existing_score then
  sequence = tonumber(sequence_raw or '0')
else
  sequence = redis.call('INCR', KEYS[3])
  local score = math.floor(created_at * {_SESSION_SCORE_SCALE}) + sequence
  local highest_scores = redis.call('ZREVRANGE', KEYS[2], 0, 0, 'WITHSCORES')
  if highest_scores[2] ~= nil and tonumber(highest_scores[2]) ~= nil and score <= tonumber(highest_scores[2]) then
    score = tonumber(highest_scores[2]) + 1
  end
  redis.call('ZADD', KEYS[2], score, ARGV[1])
end

redis.call('SET', KEYS[1], ARGV[2], 'EX', ttl_seconds)
redis.call('EXPIRE', KEYS[2], ttl_seconds)
redis.call('EXPIRE', KEYS[3], ttl_seconds)

local evicted = 0
if max_sessions > 0 then
  while redis.call('ZCARD', KEYS[2]) > max_sessions do
    local victims = redis.call('ZRANGE', KEYS[2], 0, 0)
    if #victims == 0 then
      break
    end
    local victim = victims[1]
    redis.call('DEL', 'session:' .. victim)
    redis.call('ZREM', KEYS[2], victim)
    evicted = evicted + 1
  end
end

local live_count = redis.call('ZCARD', KEYS[2])
if live_count == 0 then
  redis.call('DEL', KEYS[2])
  redis.call('DEL', KEYS[3])
end
return {{sequence, live_count, evicted}}
"""

_DELETE_INDEXED_SESSION_LUA = """
local session_type = redis.call('TYPE', KEYS[1]).ok
if session_type ~= 'none' and session_type ~= 'string' then
  return redis.error_reply('invalid-session-key-type')
end

local raw = redis.call('GET', KEYS[1])
if not raw then
  return {0, false, false, '', ''}
end

local decoded = cjson.decode(raw)
local user_id = decoded['user_id']
local actor_identity = decoded['username']
if type(user_id) ~= 'string' or user_id == '' then
  redis.call('DEL', KEYS[1])
  return {1, false, false, '', type(actor_identity) == 'string' and actor_identity or ''}
end

local index_key = 'user_sessions:' .. user_id
local sequence_key = 'user_sessions_seq:' .. user_id
local index_type = redis.call('TYPE', index_key).ok
local sequence_type = redis.call('TYPE', sequence_key).ok
if index_type ~= 'none' and index_type ~= 'zset' then
  return redis.error_reply('invalid-index-key-type')
end
if sequence_type ~= 'none' and sequence_type ~= 'string' then
  return redis.error_reply('invalid-sequence-key-type')
end
local sequence_raw = redis.call('GET', sequence_key)
if sequence_raw ~= false and string.match(sequence_raw, '^%d+$') == nil then
  return redis.error_reply('invalid-sequence-value')
end

if index_type == 'zset' then
  local members = redis.call('ZRANGE', index_key, 0, -1)
  for _, member in ipairs(members) do
    if member ~= ARGV[1] and redis.call('EXISTS', 'session:' .. member) == 0 then
      redis.call('ZREM', index_key, member)
    end
  end
end

redis.call('DEL', KEYS[1])
if index_type == 'zset' then
  redis.call('ZREM', index_key, ARGV[1])
  if redis.call('ZCARD', index_key) == 0 then
    redis.call('DEL', index_key)
    redis.call('DEL', sequence_key)
    return {1, true, true, user_id, type(actor_identity) == 'string' and actor_identity or ''}
  end
else
  redis.call('DEL', sequence_key)
  return {1, true, true, user_id, type(actor_identity) == 'string' and actor_identity or ''}
end
return {1, true, false, user_id, type(actor_identity) == 'string' and actor_identity or ''}
"""

_REFRESH_INDEXED_SESSION_LUA = f"""
local session_type = redis.call('TYPE', KEYS[1]).ok
if session_type ~= 'none' and session_type ~= 'string' then
  return redis.error_reply('invalid-session-key-type')
end

local now = tonumber(ARGV[1])
local ttl_seconds = tonumber(ARGV[2])
if now == nil then
  return redis.error_reply('invalid-refresh-time')
end
if ttl_seconds == nil or ttl_seconds <= 0 then
  return redis.error_reply('invalid-session-ttl')
end

local raw = redis.call('GET', KEYS[1])
if not raw then
  return nil
end

local decoded = cjson.decode(raw)
local original_user_id = decoded['user_id']
local replacement = nil
if ARGV[5] ~= '' then
  replacement = cjson.decode(ARGV[5])
  if type(original_user_id) == 'string' and replacement['user_id'] ~= original_user_id then
    return redis.error_reply('session-user-mismatch')
  end
  if ARGV[4] ~= '' and raw == ARGV[4] then
    decoded = replacement
  else
    decoded['role_id'] = replacement['role_id']
    decoded['role_name'] = replacement['role_name']
    decoded['permissions'] = replacement['permissions']
  end
end
local user_id = decoded['user_id']
local last_activity = tonumber(decoded['last_activity'] or '0')
local index_key = nil
local sequence_key = nil
local index_type = 'none'
local sequence_type = 'none'
local sequence_raw = false
if type(user_id) == 'string' and user_id ~= '' then
  index_key = 'user_sessions:' .. user_id
  sequence_key = 'user_sessions_seq:' .. user_id
  index_type = redis.call('TYPE', index_key).ok
  sequence_type = redis.call('TYPE', sequence_key).ok
  if index_type ~= 'none' and index_type ~= 'zset' then
    return redis.error_reply('invalid-index-key-type')
  end
  if sequence_type ~= 'none' and sequence_type ~= 'string' then
    return redis.error_reply('invalid-sequence-key-type')
  end
  sequence_raw = redis.call('GET', sequence_key)
  if sequence_raw ~= false and string.match(sequence_raw, '^%d+$') == nil then
    return redis.error_reply('invalid-sequence-value')
  end
end
if now - last_activity > ttl_seconds then
  redis.call('DEL', KEYS[1])
  if index_key ~= nil then
    if index_type == 'zset' then
      local members = redis.call('ZRANGE', index_key, 0, -1)
      for _, member in ipairs(members) do
        if member ~= ARGV[3] and redis.call('EXISTS', 'session:' .. member) == 0 then
          redis.call('ZREM', index_key, member)
        end
      end
      redis.call('ZREM', index_key, ARGV[3])
      if redis.call('ZCARD', index_key) == 0 then
        redis.call('DEL', index_key)
        redis.call('DEL', sequence_key)
      end
    else
      redis.call('DEL', sequence_key)
    end
  end
  return nil
end

if type(user_id) == 'string' and user_id ~= '' then
  if index_type == 'zset' and sequence_raw == false then
    local highest_scores = redis.call('ZREVRANGE', index_key, 0, 0, 'WITHSCORES')
    local recovered_sequence = 0
    if highest_scores[2] ~= nil and tonumber(highest_scores[2]) ~= nil then
      local scaled = tonumber(highest_scores[2])
      if scaled >= {_SESSION_SCORE_SCALE} then
        recovered_sequence = scaled - (math.floor(scaled / {_SESSION_SCORE_SCALE}) * {_SESSION_SCORE_SCALE})
      end
    end
    if recovered_sequence < redis.call('ZCARD', index_key) then
      recovered_sequence = redis.call('ZCARD', index_key)
    end
    redis.call('SET', sequence_key, math.floor(recovered_sequence))
    sequence_raw = tostring(math.floor(recovered_sequence))
  end
  if index_type == 'none' then
    redis.call('SET', sequence_key, '1')
    redis.call('ZADD', index_key, math.floor(now * {_SESSION_SCORE_SCALE}) + 1, ARGV[3])
  elseif redis.call('ZSCORE', index_key, ARGV[3]) == false then
    local sequence = redis.call('INCR', sequence_key)
    local score = math.floor(now * {_SESSION_SCORE_SCALE}) + sequence
    local highest_scores = redis.call('ZREVRANGE', index_key, 0, 0, 'WITHSCORES')
    if highest_scores[2] ~= nil and tonumber(highest_scores[2]) ~= nil and score <= tonumber(highest_scores[2]) then
      score = tonumber(highest_scores[2]) + 1
    end
    redis.call('ZADD', index_key, score, ARGV[3])
  end
end

decoded['last_activity'] = now
decoded['generation'] = tonumber(decoded['generation'] or '0') + 1
local refreshed = cjson.encode(decoded)
redis.call('SET', KEYS[1], refreshed, 'EX', ttl_seconds)
if type(user_id) == 'string' and user_id ~= '' then
  local index_key = 'user_sessions:' .. user_id
  local sequence_key = 'user_sessions_seq:' .. user_id
  if redis.call('TYPE', index_key).ok == 'zset' then
    redis.call('EXPIRE', index_key, ttl_seconds)
    redis.call('EXPIRE', sequence_key, ttl_seconds)
  end
end
return refreshed
"""


class SessionRepository:
    """Repository for chat sessions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, user_id: uuid.UUID, preview_text: str = "") -> Session:
        """Create a new session."""
        session = Session(user_id=user_id, preview_text=preview_text)
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def list_by_user(self, user_id: uuid.UUID) -> list[Session]:
        """Return sessions for a user, reverse-chronological by last_activity."""
        result = await self._session.execute(
            select(Session).where(Session.user_id == user_id).order_by(desc(Session.last_activity_at))
        )
        return list(result.scalars().all())

    async def page_by_user(
        self,
        user_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Session], str | None]:
        """Return one stable, ownership-scoped keyset page."""
        statement = (
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(desc(Session.last_activity_at), desc(Session.id))
            .limit(limit + 1)
        )
        if cursor is not None:
            position = decode_cursor(cursor, _SESSION_CURSOR_NAMESPACE)
            try:
                activity_at = datetime.fromisoformat(position.sort_value)
                if activity_at.tzinfo is None:
                    raise ValueError
            except ValueError:
                raise InvalidCursorError() from None
            statement = statement.where(
                or_(
                    Session.last_activity_at < activity_at,
                    and_(Session.last_activity_at == activity_at, Session.id < position.item_id),
                )
            )

        rows = list((await self._session.execute(statement)).scalars().all())
        if len(rows) <= limit:
            return rows, None
        page = rows[:limit]
        last = page[-1]
        return page, encode_cursor(_SESSION_CURSOR_NAMESPACE, last.last_activity_at.isoformat(), last.id)

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """Return the exact ownership-scoped session total."""
        statement = select(func.count()).select_from(Session).where(Session.user_id == user_id)
        return int((await self._session.execute(statement)).scalar_one())

    async def get_by_id(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Session | None:
        """Fetch a single session by ID and user."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a session (cascade deletes accepted_queries). Returns True if deleted."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        await self._session.delete(session)
        await self._session.flush()
        return True

    async def update_last_activity(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Update last_activity_at to now()."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        session.last_activity_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def update_preview_text(self, session_id: uuid.UUID, user_id: uuid.UUID, preview_text: str) -> bool:
        """Update preview text (truncated to 60 chars + ellipsis)."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        truncated = preview_text if len(preview_text) <= 60 else preview_text[:60] + "..."
        session.preview_text = truncated
        await self._session.flush()
        return True

    async def update_connection(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> Session | None:
        """Update session's selected connection (T-434, FR-094)."""
        result = await self._session.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        session.connection_id = connection_id
        session.last_activity_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    @staticmethod
    async def create_indexed_session(
        redis: Redis,
        request: IndexedSessionCreateRequest,
    ) -> IndexedSessionCreateResult:
        """Create a session key and enforce the per-user index atomically."""
        keys_and_args: tuple[Any, ...] = (
            _session_key(request.session_id),
            _user_index_key(request.user_id),
            _user_sequence_key(request.user_id),
            request.session_id,
            request.session_json,
            str(float(request.created_at)),
            str(int(request.max_sessions)),
            str(int(request.ttl_seconds)),
            request.user_id,
        )
        sequence, live_count, evicted_count = await redis.eval(_CREATE_INDEXED_SESSION_LUA, 3, *keys_and_args)
        return IndexedSessionCreateResult(
            sequence=int(sequence),
            live_indexed_sessions=int(live_count),
            evicted_sessions=int(evicted_count),
        )

    @staticmethod
    async def delete_indexed_session(redis: Redis, session_id: str) -> IndexedSessionDeleteResult:
        """Delete a session key and matching user-index member atomically."""
        session_deleted, user_found, index_empty, user_id, actor_identity = await redis.eval(
            _DELETE_INDEXED_SESSION_LUA,
            1,
            _session_key(session_id),
            session_id,
        )
        return IndexedSessionDeleteResult(
            actor_identity=actor_identity or None,
            user_id=user_id or None,
            session_deleted=bool(session_deleted),
            index_empty=bool(index_empty),
        )

    @staticmethod
    async def refresh_indexed_session(
        redis: Redis,
        request: IndexedSessionRefreshRequest,
    ) -> str | None:
        """Refresh session JSON atomically without recreating an evicted key."""
        refreshed_session = await redis.eval(
            _REFRESH_INDEXED_SESSION_LUA,
            1,
            _session_key(request.session_id),
            str(float(request.now)),
            str(int(request.ttl_seconds)),
            request.session_id,
            request.expected_session_json or "",
            request.replacement_session_json or "",
        )
        return refreshed_session if isinstance(refreshed_session, str) else None
