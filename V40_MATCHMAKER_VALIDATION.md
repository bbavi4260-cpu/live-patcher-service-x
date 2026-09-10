# Sigma V40 matchmaking compatibility update

The supplied Assembly-CSharp decompilation exposed the TCP transport envelope and matchmaking command names. `TCPMsgPacket` uses a one-byte protocol command, one-byte region, and a four-byte little-endian payload length. `EProtocol.MATCHMAKING` is protocol 3. `EMatchmaking.Proto_START` is subcommand 1, `Proto_MATCHMAKINGSUSS_NTF` is subcommand 5, and `Proto_START_NTF` is subcommand 12.

`game_node.py` now parses complete framed packets, logs protocol/region/length/subcommand, and has an optional compatibility matchmaker. When `--matchmaker` is enabled and a protocol-3/subcommand-1 packet arrives, the node sends a start notification and then a success notification using the recovered `MatchmakingSussNtf` field order. The success packet contains a generated match ID, advertised game-server address, generated compatibility tokens, default map/mode values, and empty workshop fields. The launcher enables this mode by default.

This is a conservative single-player compatibility path. It is intended to move the client past the matchmaking transition, not to provide a real multi-player gameplay server. The actual game-node gameplay protocol, authentication/encryption handshake, map loading, and multi-player room synchronization remain outside the decompiled method bodies and are not fabricated.

For a remote server, start with `SIGMA_PUBLIC_HOST=<server-ip> bash termux_start_server.sh`. For the same device, use `bash termux_start_server.sh`. The advertised address is written into `MatchmakingSussNtf`; ports 3000, 10300, and 10101 must be reachable from the client.

Local validation passed: Python bytecode compilation, shell syntax check, and a framed TCP smoke test. The smoke test received two protocol-3 response frames and the JSONL log recorded `matchmaking_start_sent` and `matchmaking_success_sent`.
