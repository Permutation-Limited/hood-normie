# Local web app

A locally hosted browser view over the same read-only tools the CLI uses. A
Python server hosts the built single-page app and answers a small JSON API; the
app is React + TypeScript + MUI, routed with TanStack Router and fetching with
TanStack Query. Everything builds under Bazel.

Each tab is one of the command-line tools:

| Tab | Endpoint | Command-line equivalent |
| --- | --- | --- |
| Accounts | `/api/accounts` | `bazel run //examples:list_accounts` |
| Holdings | `/api/holdings` | `bazel run //examples:list_holdings` |
| Rebalance | `/api/rebalance` | `bazel run //examples/rebalance` |

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

## Sorting, searching, and CSV export

Every column header sorts, and each holdings table and the account list carry a
search box that filters on any column. Money and quantities sort numerically —
`$9,830` above `$85,650` would be the string answer, not the useful one — and
values Robinhood did not return sort last rather than as empty text. Sorting a
column that has unavailable entries ascending therefore keeps them out of the
way. Sort and search state is per-table and lives in component state, not the
URL: it changes nothing about which numbers are shown.

Each table's `CASH` and `TOTAL` rows are the account's own, so they stay put and
keep their full value while a filter narrows the rows above them.

Every table also has a **CSV** button, which exports exactly what is on screen —
current filter and column order included. The download holds the API's exact
decimal strings rather than the formatted display text, so a spreadsheet
receives `1000.50`, not `$1,000.50`, and a column totals without cleanup.
Holdings exports carry the `CASH` and `TOTAL` rows the table shows; plan exports
keep the sign on `Amount`, as the JSON does.

Demo exports say so in the filename
(`hood-normie-holdings-…-demo-2026-08-13.csv`) — a CSV outlives the page that
produced it and carries no banner, so the filename is the only place left to
mark invented numbers.

Fields that a spreadsheet would evaluate rather than display (`=`, `@`, and the
like) are prefixed with a quote on the way out; negative amounts are exempt,
since they are data. `//webapp/frontend:csv_test` covers that and the quoting
rules.

## Demo mode

The **Demo** chip in the header replaces your accounts with invented ones:

```
http://127.0.0.1:8765/rebalance?demo=1
```

The chip is both the indicator and the switch, and it always names the state you
are in rather than the one it would switch to: filled amber "Demo data" on, a
quiet outlined "Live data" off. A glance at the header answers "am I looking at
my own money?" without interpreting a control. It is the only place the app says
anything about demo mode, so no second badge or banner can disagree with it, and
it stays on screen on every tab.

The state lives in the URL, so a demo view is linkable, survives a reload, and
follows you across navigation — a live URL can never be showing demo numbers or
the reverse. Every demo response also carries `"demo": true`; CSV exports are
named from that field, so a downloaded demo file says so in its filename.

A demo request reads `webapp/demo_config.yaml` and the invented snapshot in
`webapp/demo.py`, whose `ACCOUNTS` records stand in for `get_accounts` on the
Accounts and Holdings tabs. It contacts nothing, reads no token, and never opens your
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
| `server.py` | HTTP server: static assets, SPA fallback, the `/api` endpoints |
| `api.py` | Report-to-JSON serialization |
| `demo.py`, `demo_config.yaml` | Invented data behind the header's Demo chip |
| `frontend/` | Vite + React + TypeScript sources |

The numbers come from `//examples/rebalance:report` and
`RobinhoodClient.fetch_holdings`, the same modules the terminal tools render
from, so the browser and the CLI cannot disagree.

## The API

Every endpoint runs one live fetch per request and takes `?demo=1` for invented
data. Money is always a decimal string, never a JSON number, so exact cents
survive the trip.

`GET /api/accounts` lists the accounts the token can read. A field is `null`
where Robinhood returned nothing; the CLI prints `(unavailable)` for the same
case.

```json
{
  "generated_at": "2026-08-13T22:57:53.974583+00:00",
  "demo": false,
  "accounts": [
    {"tax_status": "individual", "account_type": "margin",
     "account_number": "111", "nickname": null}
  ]
}
```

`GET /api/holdings` marks each account's equity positions at the latest quote.
`total_value` is the marked positions plus cash, so the rows add up to the total
shown beneath them rather than to a separately reported broker figure.

```json
{
  "generated_at": "2026-08-13T22:57:53.974583+00:00",
  "demo": false,
  "grand_total": "2050",
  "accounts": [
    {
      "label": "individual · Main · 111",
      "account_number": "111",
      "cash": "1000",
      "total_value": "2050",
      "positions": [
        {"symbol": "VTI", "quantity": "10", "price": "100",
         "market_value": "1000"}
      ]
    }
  ]
}
```

`GET /api/rebalance` returns one object per configured portfolio:

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

Unlike the CLI's `--json`, `amount` keeps its sign; `action` carries the same
direction either way.

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
`//webapp/frontend:smoke_test` asserts the bundle is servable,
`//webapp/frontend:csv_test` and `//webapp/frontend:sorting_test` cover CSV
serialization and table sorting, and
`//webapp:server_test` covers the API and the static handler, including directory
traversal attempts.
