# Sigma V37 Minimum Profile-Response Compatibility Test

This package is an explicit nearby-version source-default revision. It imports
the uploaded FreeFireServer's literal default profile roster, selected Adam
clothes/skin state, source `items.json` ownership corpus, and source free store
sample. The matched Sigma 1.0.113 client/source proto supplies every emitted
response envelope and field.

It preserves V29's working lobby and Vault source-default state, the verified
V25 non-empty hide-avatar response, V30's skill projection, V30's matching
51-profile cardinality, and V31's non-null `GetPlayerTCStats` plus declared
empty `GetBattleTag` response.

V32 added only the two 404 routes proved by the V31 screen recording and same-run
log: `GetMatchStatsHistory` returns an empty declared `CSGetMatchStatsListRes`,
and `GetPlayerStats` returns non-null zeroed solo, duo, and quad statistics for
the canonical local account. It does not fabricate match records.

V33 adds one confirmed structural field to the retained `GetPlayerTCStats`
response. Sigma declares `AccountInfoWithTCStats.detailed_stats` at nested field
5. V33 makes that `DetailedTCStats` message present but empty (`2a00`), keeping
all ten Clash-Squad counters at protobuf zero. The complete response is exactly
`0a070881c2d72f2a00`. It does not add match records, wins, kills, ranks, ratings,
or any fabricated resource data.

V34 addresses the exact same-run re-login boundary recorded on the phone. After
all lobby/Profile routes returned HTTP 200, `SetPregameShowChoices` and
`UpdateSocialBasicInfo` returned 404 immediately before OAuth inspect and the
client’s “please re-login” message. V34 adds only their declared contracts:
`SetPregameShowChoices` receives an empty protobuf acknowledgement because no
response type is declared, and `UpdateSocialBasicInfo` returns
`CSSocialBasicInfoRes.info` containing only the canonical account ID
(`0a050881c2d72f`). It does not persist or invent social settings, tags,
signature, preferences, or pregame choices.

V35 addresses the subsequent no-HTTP-error re-login boundary. `LoginRes`
advertises a persistent notification channel at `127.0.0.1:10300`, but V34
started no listener there. V35 starts a local TCP presence listener alongside
HTTP. It accepts a complete opaque Cmd=1 auth frame and returns only bare
`0x02`; it returns the same bare `0x02` for Cmd=2 heartbeats. The listener logs
only command metadata and encrypted length. It does **not** decrypt, store, or
log session tokens or payloads, and it does not implement notification pushes,
matchmaking, the port-10101 realtime game node, or any fabricated packet.

V36 restores the omitted **source account lifecycle state** that feeds the
Profile screen and visible selected-avatar state. The previous V35 package kept
the source profile roster and inventory, but it projected a different hardcoded
LoginData snapshot, emitted only avatar/skin/clothes from SelectedItems, and
returned only an empty AccountPrefers placeholder for Personal Show basic info.
That is why the Profile screen displayed UID 0, level 0, and empty-looking
presentation fields.

V36 projects the literal FreeFireServer default account values through matched
Sigma tags: level 100, 250000 exp, rank 1, 1000 ranking points, 999999 wallet
currency, banner 900000014, head picture 902000003, two source loadouts, and
the source skill-slot layout. It keeps selected profile and SelectedItems in
sync after selection or clothes changes. `GetBackpack` now returns the supported
full SelectedItems state, while `GetPlayerPersonalShow` returns full
AccountInfoBasic plus the selected AvatarProfile and source default EP-history
entries. No match records, social tags, battle tags, or resource configuration
data is invented.

V37 keeps the V36 source-default LoginData and complete Backpack SelectedItems
state, but reduces only `GetPlayerPersonalShow` after V36 blanked the Profile
scene. It retains source `AccountInfoBasic` and the selected AvatarProfile, then
restores V35's present empty `DiamondCostRes` at top-level field 10. It omits
only V36's added top-level ranking-position and repeated EP-history fields. This
is a bounded Sigma-version response-shape compatibility test, not a reversal of
the source-first lifecycle.

Character is an independent unresolved client-side configuration dependency:
the source provides owned skill IDs, while the matched Sigma Character cards
also require separate avatar-skill definition data not present in the preserved
local resources or nearby source archive.

The `resources` directory may contain only byte-for-byte local preserved Sigma
`fileinfo` and `config/avatar` artifacts. Their routes are passive; this package
 does not invent a resource scheduler or descriptor.

## Termux live logs

The bundled `termux_start_server.sh` now runs the HTTP compatibility server and notification listener while keeping the terminal attached to a live, prefixed log stream. HTTP activity appears with the `[HTTP]` prefix, and notification-channel metadata appears with `[NOTIFY]`. The same output is also persisted under `logs/console.log` and `logs/notification.console.log`.

From Termux, run:

```bash
cd sigma_test_server_v37_minimum_profile_response
chmod +x termux_start_server.sh termux_stop_server.sh
bash termux_start_server.sh
```

Keep that terminal open to watch live logs. Press `Ctrl-C` to stop both services cleanly. From another Termux session, the services can also be stopped with:

```bash
cd sigma_test_server_v37_minimum_profile_response
bash termux_stop_server.sh
```

To follow only one persistent log file without starting the services again, use `tail -f logs/console.log` for HTTP requests or `tail -f logs/notification.console.log` for notification events. The notification output remains metadata-only and does not print tokens or encrypted payload contents.

### Optional ports

The default HTTP port is `3000`, and the notification port is `10300`. Override them before starting if needed:

```bash
SIGMA_TEST_PORT=3000 SIGMA_NOTIFICATION_PORT=10300 bash termux_start_server.sh
```

The server binds to `0.0.0.0` by default so a client on the same device or local network can reach it. Set `SIGMA_TEST_HOST=127.0.0.1` when local-device-only access is preferred. The address advertised inside `LoginRes` defaults to `127.0.0.1`; when the client and server are on different devices, set `SIGMA_PUBLIC_HOST` to the server's LAN IP and ensure ports `3000`, `10300`, and `10101` are reachable. For example: `SIGMA_PUBLIC_HOST=192.168.1.20 bash termux_start_server.sh`.

The startup script also exposes the advertised realtime game-node port `10101` (override with `SIGMA_GAME_NODE_PORT`). It accepts opaque TCP connections and logs connection/frame metadata to the terminal with the `[GAME_NODE]` prefix and to `logs/game_node.jsonl`. Because the exact encrypted gameplay protocol is not present in the preserved evidence, this listener does not fabricate map, room, matchmaking, or gameplay responses; it provides the missing connection boundary and makes the client’s next request visible in live logs.

## Full local project package

This package contains the local compatibility server code, TCP/UDP listeners, startup scripts, documentation, and the complete `resources/` tree from the supplied project. Runtime logs and the supplied account/session state were not copied; a synthetic local test fixture is provided instead. Use only with a client and assets you own or are authorized to test.
