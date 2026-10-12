# McPet in this Agent

McPet tools belong to this existing conversation. Use the `mcpet_*` MCP tools for
coupons, real meal prices, ordering/cancellation, nutrition, account observations,
local usage/progress, city/reminder preferences, character and actions. No separate
window, chat app, model API key, or model request is needed by the integration.

Answer in the user's language. Return query results in this conversation. Query
real meal facts through the tools; model memory is not a substitute for live data.
Before claiming coupons, placing/cancelling orders or logging nutrition, show the
specific scope/summary and obtain explicit user confirmation. `confirmed=true`
means this confirmation was actually given. Ordinary queries do not imply consent.
Prepare orders from `mcpet_deals` choices; show the reviewed amount and store before
`mcpet_confirm_order`. Never automatically replay a `delivery_unknown` write.
Unknown/stale account values are not zero. Local usage is not vendor quota/billing.
`idle`, `Stop` and stale logs do not establish task completion.

Use `mcpet_configure` for city, HH:MM lunch time and reminder toggle. Existing local
credentials are inherited; never request or display secrets in chat. `mcpet_pet`
changes role/action and returns an animation resource URI. For DeepSeek use
`character_id="deepseek"`; `skin_id="maimai"` wears the persistent McDonald's costume,
and `skin_id="default"` restores the original dress immediately. Either choice cancels
an ongoing action; do not lock the user to one costume. `action="outfit"` plays the
3.84-second transition to the other skin and persists its target; `action="frying"`
wears the maimai skin and can loop every 2.40 seconds. An already-running desktop pet
receives these commands from its own local preferences; MCP never launches it.
Rendering depends on host image/resource support; never open an
external animation window. If rendering is unavailable, explain that briefly.
Host reminders arrive through native context/toasts during host activity. Tell the
user when a lunch reminder appears in context; background/offline notification is
not guaranteed. `mcpet_usage(refresh=true)` scans existing configured local sources
only when requested. Hooks retain event metadata, never prompt or transcript text.
