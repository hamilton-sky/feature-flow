# Brainstorm: <feature>

Picked by: <person|agent>
Style: <route|blueprint|sketch|paper|terminal|bright>

## Idea

<The ask in the user's words, and the answers to the questions you asked.>

## What exists

<What the scouts found and you checked: the nearest existing code, the files that would change. Mark what you did not check as unverified.>

## Options

### A. <name>

```mermaid
flowchart LR
  User[User] --> Api[New endpoint]
  Api --> Store[(Existing store)]
  classDef orange fill:#fbe8da,stroke:#d0661a
  classDef blue fill:#e0eafb,stroke:#2f6fdb
  classDef green fill:#e1f1e3,stroke:#2f8a3e
  class User orange
  class Api blue
  class Store green
```

- Pros: <...>
- Cons: <...>
- Size: <tickets, or S, M, L>
- Risky areas: <auth, secrets, money, data loss, limits, hostile input; or none>

### B. <name>

<Same shape.>

## Chosen

<A or B, and why, in the user's words where you can. The planner copies its diagram into spec.md's Design.>

## Rejected

- <B>: <one line on why, so nobody re-opens it>

## Consulted

<Answers from the architect, designer or product owner, or none.>

## Risks for the planner

<Areas of the chosen option that should be level 3 or on the Sensitive: line.>

## Open

<What still needs an answer. It goes under Unsure in the brief.>
