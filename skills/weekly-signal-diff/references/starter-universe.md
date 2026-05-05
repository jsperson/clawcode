# Starter Universe

Use this file only when the user has not already defined a watchlist. The list
below is a bootstrap scaffold, not a hard requirement.

Rules for using it:

- Start here only if the user has not provided categories, companies, or a
  source packet.
- Treat the categories and entities as suggested defaults.
- Re-rank, replace, or expand the list using QMD context and prior Trends
  entries before you write the final diff.
- Preserve some baseline discovery. Do not personalize so aggressively that the
  scan stops surfacing new signal.

## Technology / AI

| Category | Suggested Entities |
| -------- | ------------------- |
| Frontier labs | OpenAI, Anthropic, Google DeepMind |
| Open model ecosystem | Meta AI, Mistral, Hugging Face |
| Search and answer interfaces | Perplexity, Glean, You.com |
| Developer tooling and agents | Cursor, Replit, Cognition |
| Cloud AI platforms | Microsoft Azure AI, Google Cloud, AWS |
| Data and model infrastructure | Databricks, Snowflake, Together AI |
| Enterprise software incumbents | Salesforce, Atlassian, ServiceNow |
| Productivity and knowledge tools | Notion, Canva, Grammarly |
| Creative media generation | Runway, ElevenLabs, Pika |
| Robotics and embodied AI | Figure, Wayve, Physical Intelligence |

## Geopolitics

| Category | Suggested Entities |
| -------- | ------------------- |
| Active conflicts | Iran/Hormuz, Ukraine-Russia, Israel-Lebanon |
| Great power competition | US-China trade, NATO/EU defense spending, BRICS expansion |
| Trade and sanctions | Section 301, IEEPA/Section 122, semiconductor export controls |

## Macro Economics

| Category | Suggested Entities |
| -------- | ------------------- |
| Growth indicators | GDP, PMI, retail sales |
| Monetary policy | Federal Reserve (FOMC), ECB, BOJ |
| Inflation | CPI, PCE, energy pass-through |
| Labor market | Payrolls, participation rate, ADP, tech layoffs |

## Financial Stability

| Category | Suggested Entities |
| -------- | ------------------- |
| Banking stress | CDS spreads, loan loss provisions, CRE exposure |
| Credit markets | IG/HY spreads, corporate refinancing, S&P Credit Cycle Indicator |
| Sovereign and EM risk | IMF warnings, EM capital flows, currency stress |
| Treasuries | Yield curve shape, 10Y/2Y/30Y levels, Fed repo facility |

## Market Volatility Signals

| Category | Suggested Entities |
| -------- | ------------------- |
| Volatility surface | VIX, VVIX, skew, oil implied vol |
| Dealer positioning | Gamma exposure, OpEx flows, squeeze events |
| Cross-asset warnings | Yen carry (USD/JPY), DXY, correlation breaks |
| Catalyst calendar | FOMC, CPI releases, earnings clusters, OpEx dates |

## Consumer Credit Health

| Category | Suggested Entities |
| -------- | ------------------- |
| Card metrics | BofA delinquency/charge-off rates, revolving credit totals |
| Consumer stress | FICO distribution, auto loan delinquency, mortgage stress |
| Spending patterns | NRF forecasts, credit utilization trends, K-shaped divergence |

## Re-Ranking Heuristics

Promote an entity or category when:

- it shows up repeatedly in the user's projects or vault captures
- it affects a toolchain or market the user depends on
- it competes with, supplies, or constrains something the user is building or tracking
- it appeared in the last diff and has unresolved momentum

Demote or replace an entity or category when:

- it has low connection to the user's actual work or situation
- it generates plenty of headlines but little structural change
- the user's focus clearly lives elsewhere

## Coverage Note Template

Use wording like this at the top of the weekly diff summary:

`This week's scan covered [N] domains and [N] tracked entities, reweighted using vault context around [focus areas].`
