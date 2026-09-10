#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

PORT="${SIGMA_TEST_PORT:-3000}"
HOST="${SIGMA_TEST_HOST:-0.0.0.0}"
NOTIFICATION_PORT="${SIGMA_NOTIFICATION_PORT:-10300}"
GAME_NODE_PORT="${SIGMA_GAME_NODE_PORT:-10101}"
UDP_PORT="${SIGMA_UDP_PORT:-10102}"
# The client receives this address inside LoginRes. Override it when the
# server runs on another phone/PC; 127.0.0.1 is correct only on the same device.
ADVERTISED_HOST="${SIGMA_PUBLIC_HOST:-127.0.0.1}"
export SIGMA_GAME_NODE="${SIGMA_GAME_NODE:-${ADVERTISED_HOST}:${GAME_NODE_PORT}}"
export SIGMA_NOTIFICATION_CHANNEL="${SIGMA_NOTIFICATION_CHANNEL:-${ADVERTISED_HOST}:${NOTIFICATION_PORT}}"

mkdir -p logs data resources

if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE ":${PORT}[[:space:]]"; then
  echo "HTTP port ${PORT} is already occupied."
  echo "Run: bash termux_stop_server.sh"
  exit 1
fi
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE ":${NOTIFICATION_PORT}[[:space:]]"; then
  echo "Notification port ${NOTIFICATION_PORT} is already occupied."
  echo "Run: bash termux_stop_server.sh"
  exit 1
fi
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE ":${GAME_NODE_PORT}[[:space:]]"; then
  echo "Game-node port ${GAME_NODE_PORT} is already occupied."
  echo "Run: bash termux_stop_server.sh"
  exit 1
fi
if command -v ss >/dev/null 2>&1 && ss -lun 2>/dev/null | grep -qE ":${UDP_PORT}[[:space:]]"; then
  echo "UDP heartbeat port ${UDP_PORT} is already occupied."
  echo "Run: bash termux_stop_server.sh"
  exit 1
fi

rm -f logs/server.pid logs/notification.pid logs/udp2.pid

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping Sigma services..."
  [ -n "${HTTP_TAIL_PID:-}" ] && kill "$HTTP_TAIL_PID" 2>/dev/null || true
  [ -n "${NOTIFY_TAIL_PID:-}" ] && kill "$NOTIFY_TAIL_PID" 2>/dev/null || true
  [ -n "${GAME_TAIL_PID:-}" ] && kill "$GAME_TAIL_PID" 2>/dev/null || true
  [ -n "${UDP_TAIL_PID:-}" ] && kill "$UDP_TAIL_PID" 2>/dev/null || true
  [ -s logs/server.pid ] && kill "$(cat logs/server.pid)" 2>/dev/null || true
  [ -s logs/notification.pid ] && kill "$(cat logs/notification.pid)" 2>/dev/null || true
  [ -s logs/game_node.pid ] && kill "$(cat logs/game_node.pid)" 2>/dev/null || true
  [ -s logs/udp2.pid ] && kill "$(cat logs/udp2.pid)" 2>/dev/null || true
  rm -f logs/server.pid logs/notification.pid logs/game_node.pid logs/udp2.pid
  echo "Sigma HTTP and notification services stopped."
  exit 0
}
trap cleanup INT TERM EXIT

python3 -u notification_gateway.py --host "$HOST" --port "$NOTIFICATION_PORT" --log-dir "$PWD/logs" > logs/notification.console.log 2>&1 &
NOTIFICATION_PID=$!
echo "$NOTIFICATION_PID" > logs/notification.pid

python3 -u game_node.py --host "$HOST" --port "$GAME_NODE_PORT" --log-dir "$PWD/logs" --matchmaker --advertised-addr "${SIGMA_GAME_NODE}" > logs/game_node.console.log 2>&1 &
GAME_NODE_PID=$!
echo "$GAME_NODE_PID" > logs/game_node.pid

python3 -u udp2.py --host "$HOST" --port "$UDP_PORT" --log "$PWD/logs/udp2.jsonl" > logs/udp2.console.log 2>&1 &
UDP_PID=$!
echo "$UDP_PID" > logs/udp2.pid

python3 -u test_server.py --host "$HOST" --port "$PORT" --root "$PWD" > logs/console.log 2>&1 &
HTTP_PID=$!
echo "$HTTP_PID" > logs/server.pid

sleep 1
if ! kill -0 "$HTTP_PID" 2>/dev/null || ! kill -0 "$NOTIFICATION_PID" 2>/dev/null || ! kill -0 "$GAME_NODE_PID" 2>/dev/null || ! kill -0 "$UDP_PID" 2>/dev/null; then
  echo "Server failed to start. See logs/console.log and logs/notification.console.log"
  cleanup
fi

echo "Sigma V40 matchmaking compatibility server started."
echo "HTTP PID: $HTTP_PID"
echo "Notification PID: $NOTIFICATION_PID"
echo "Game-node PID: $GAME_NODE_PID"
echo "HTTP listener: ${HOST}:${PORT}"
echo "Notification listener: ${HOST}:${NOTIFICATION_PORT}"
echo "Game-node listener: ${HOST}:${GAME_NODE_PORT}"
echo "UDP heartbeat listener: ${HOST}:${UDP_PORT}"
echo "Live logs are shown below. Press Ctrl-C to stop both services."
echo "Persistent logs: $PWD/logs"
echo

# Follow both output files in the foreground. This keeps logs visible in Termux.
tail -n 0 -F logs/console.log &
HTTP_TAIL_PID=$!
tail -n 0 -F logs/notification.console.log &
NOTIFY_TAIL_PID=$!
tail -n 0 -F logs/game_node.console.log &
GAME_TAIL_PID=$!
tail -n 0 -F logs/udp2.console.log &
UDP_TAIL_PID=$!

wait
