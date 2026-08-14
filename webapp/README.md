# Local web app

A locally hosted browser view over the same read-only rebalancer the CLI uses.
A Python server hosts the built single-page app and answers a small JSON API; the
app is React + TypeScript + MUI, routed with TanStack Router and fetching with
TanStack Query. Everything builds under Bazel.

It **does not place orders**. There is no endpoint that could.

## Run it

```sh
bazel run //webapp:server
```

Then open <http://127.0.0.1:8765>. The server builds the SPA as a dependency, so
a plain `bazel run` is enough after a fresh checkout.

Flags mirror the CLI: `--config PATH`, `--token-file PATH`, `--endpoint URL`,
`--verbose`, plus `--port` (default `8765`) and `--static DIR` to serve a bundle
from somewhere other than the Bazel output.

Authentication is shared with the CLI — the same token file, created by:

```sh
bazel run //examples:authenticate
```

## Demo mode

The **Demo** switch in the header replaces your accounts with invented ones:

```
http://127.0.0.1:8765/rebalance?demo=1
```

The state lives in the URL, so a demo view is linkable, survives a reload, and
follows you across navigation — a live URL can never be showing demo numbers or
the reverse. Every demo response also carries `"demo": true`, and the page labels
itself from that field rather than from the URL, so the banner reflects what the
server actually computed.

A demo request reads `webapp/demo_config.yaml` and the invented snapshot in
`webapp/demo.py`. It contacts nothing, reads no token, and never opens your
`config.yaml`, so demo mode works on a machine that has never authenticated. The
computation is the real one — same report module as a live run — so the demo
exercises margin cash targets, a fixed-dollar class, an ignored class, an
undeclared class that therefore targets $0, an external account, and an unmapped
holding.

Edit those two files to change what the demo shows. `//webapp:server_test` checks
that every demo holding has a quote, so an added symbol without a price fails the
build rather than the page.

## Layout

| Path | What it is |
| --- | --- |
| `server.py` | HTTP server: static assets, SPA fallback, `/api/rebalance` |
| `api.py` | Report-to-JSON serialization |
| `demo.py`, `demo_config.yaml` | Invented data behind the header's Demo switch |
| `frontend/` | Vite + React + TypeScript sources |

The numbers come from `//examples/rebalance:report`, the same module the terminal
rebalancer renders from, so the browser and the CLI cannot disagree.

## The API

`GET /api/rebalance` runs a live fetch and returns one object per configured
portfolio. Add `?demo=1` for invented data:

```json
{
  "generated_at": "2026-08-13T22:57:53.974583+00:00",
  "demo": false,
  "grand_total": "3700",
  "portfolios": [
    {
      "name": "taxable",
      "total_value": "2800",
      "target_cash": "-200",
      "minimum_trade": "5",
      "accounts": [
        {
          "label": "111",
          "kind": "robinhood",
          "cash": "1000",
          "total_value": "2100",
          "positions": [
            {"symbol": "VTI", "asset_class": "stocks", "quantity": "10",
             "price": "100", "market_value": "1000"}
          ]
        }
      ],
      "recommendations": [
        {"asset_class": "stocks", "action": "BUY", "amount": "720.00",
         "current_value": "1600.00", "target_value": "2320.00", "ignored": false}
      ],
      "unclassified": []
    }
  ]
}
```

Money is always a decimal string, never a JSON number, so exact cents survive the
trip. Unlike the CLI's `--json`, `amount` keeps its sign; `action` carries the
same direction either way.

Errors return a JSON `error` field: `400` for a bad or missing config, `401` when
the OAuth token needs refreshing, `502` when Robinhood is unreachable. Demo
requests raise none of these, since they read neither config nor network.

## Why it binds to loopback

The report contains account numbers, balances, and positions, and nothing
authenticates the caller. The listener is therefore fixed to `127.0.0.1` and
responses are `Cache-Control: no-store`. Do not put this behind a tunnel or a
reverse proxy without adding authentication first.

## Frontend development

The Bazel build is the source of truth, but Vite's dev server gives you hot
reload against a running API:

```sh
bazel run //webapp:server          # in one terminal, serves the API on 8765
bazel run -- @pnpm//:pnpm --dir "$PWD/webapp/frontend" install
bazel run -- @pnpm//:pnpm --dir "$PWD/webapp/frontend" dev
```

`pnpm` comes from Bazel, so no Node installation is required on the host. After
changing dependencies in `package.json`, regenerate the lockfile:

```sh
bazel run -- @pnpm//:pnpm --dir "$PWD/webapp/frontend" install --lockfile-only
```

Packages that run install scripts must be listed in
`webapp/frontend/pnpm-workspace.yaml` under `allowBuilds`, or `npm_translate_lock`
fails the build.

Tests:

```sh
bazel test //webapp/...
```

`//webapp/frontend:typecheck` runs `tsc --noEmit` in strict mode,
`//webapp/frontend:smoke_test` asserts the bundle is servable, and
`//webapp:server_test` covers the API and the static handler, including directory
traversal attempts.
