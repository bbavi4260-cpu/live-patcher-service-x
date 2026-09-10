# Sigma V42 tutorial loading fix

The tutorial loading regression was traced to the online game-node response shape. The client-side lobby handler is wired through `proto.MessageNotify`, whose fields are `account_id`, `protocol`, `ret`, `cmd`, and `content`. The previous compatibility node sent the inner matchmaking payload directly, which could leave the tutorial/game loading spinner active even though the TCP connection and frame were valid.

The matchmaking start, success, and stop responses now use the recovered `MessageNotify` envelope. The start notification uses command 12, the success notification uses command 5, and the stop notification uses command 15 under protocol 3. The existing framed transport remains unchanged.

A fresh local test on an unused port received two response frames: the start notification frame and the success notification frame. The JSONL log recorded both `matchmaking_start_sent` and `matchmaking_success_sent`. This addresses the server-side loading transition. The actual tutorial map/gameplay scene still requires the client’s supported map assets and gameplay node; the server does not fabricate gameplay packets.
