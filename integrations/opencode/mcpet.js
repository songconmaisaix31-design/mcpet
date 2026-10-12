// Installer substitutes only these two JSON string literals with local paths.
import { execFile } from "node:child_process"

const python = __MCPET_PYTHON__
const hook = __MCPET_HOOK__

function record(payload) {
  return new Promise((resolve) => {
    const child = execFile(python, [hook, "--host", "opencode"],
      { windowsHide: true, timeout: 5000, maxBuffer: 16384 }, (error, stdout) => {
        if (error) return resolve({ messages: [] })
        try { resolve(JSON.parse(stdout)) } catch { resolve({ messages: [] }) }
      })
    child.on("error", () => resolve({ messages: [] }))
    child.stdin?.on("error", () => {})
    child.stdin?.end(JSON.stringify(payload))
  })
}

export const McPet = async ({ client, directory }) => {
  let queue = Promise.resolve()
  return {
    event: async ({ event }) => {
      const properties = event.properties || {}
      let state
      let usage
      if (event.type === "session.status") {
        state = { busy: "working", idle: "idle", retry: "waiting" }[properties.status?.type]
      } else if (event.type === "session.idle") state = "idle"
      else if (event.type === "session.error") state = "error"
      else if (event.type === "session.created") state = "idle"
      else if (["permission.asked", "permission.updated"].includes(event.type)) state = "waiting"
      else if (event.type === "message.updated") {
        const info = properties.info
        if (info?.role !== "assistant" || !info.time?.completed) return
        state = "UNKNOWN" // a completed model message is not task completion
        usage = { message_id: info.id, model: info.modelID, completed_at: info.time.completed,
                  input: info.tokens?.input, output: info.tokens?.output,
                  cacheRead: info.tokens?.cache?.read, cacheWrite: info.tokens?.cache?.write }
      }
      if (!state) return
      const session = properties.sessionID || properties.info?.sessionID || properties.info?.id
      if (typeof session !== "string") return
      // Never pass prompt, message, tool arguments, errors, or transcript paths.
      const payload = { session_id: session, state, cwd: directory, ...(usage ? { usage } : {}) }
      queue = queue.then(async () => {
        const result = await record(payload)
        for (const message of result.messages || []) {
          await client.tui.showToast({ body: { title: "McPet", message, variant: "info" } })
        }
      }).catch(() => {})
      await queue
    },
  }
}
