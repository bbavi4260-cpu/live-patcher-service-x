# V39 SigmaX Max network advertisement fix

The supplied post-login capture shows successful HTTP login/profile calls but no new HTTP request after the Tap-to-Begin screen. The server's `LoginRes` advertises the realtime node address, so a wrong advertised host can make the client appear unresponsive even when the HTTP server is healthy.

The startup script now supports:

```bash
SIGMA_PUBLIC_HOST=192.168.1.20 bash termux_start_server.sh
```

`SIGMA_PUBLIC_HOST` is inserted into the advertised `SIGMA_GAME_NODE` and `SIGMA_NOTIFICATION_CHANNEL` addresses. Use the server device's LAN IP, not the client's IP. If client and server run on the same device, leave the default `127.0.0.1`. Make sure ports `3000`, `10300`, and `10101` are reachable through the local firewall/router.

This change fixes an address-reachability problem only. The current `10101` process remains an opaque listener; it does not fabricate encrypted matchmaking or gameplay packets. If the address is correct but the lobby still does not open, capture the `game_node.console.log` lines immediately after tapping.

## Validation

The patched Python files pass syntax compilation. The previous V38 route smoke test passed for the three SigmaX Max CS-ranking endpoints. The V39 shell change was reviewed for correct environment propagation to the HTTP process.

*Prepared by Manus AI.*
