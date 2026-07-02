<script>
  let messages = [];
  let input = '';
  let loading = false;
  let documents = [];
  let showDocs = false;
  let darkMode = true;

  function toggleTheme() {
    darkMode = !darkMode;
    document.body.classList.toggle('light', !darkMode);
  }

  const API_URL = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000';

  async function send() {
    if (!input.trim() || loading) return;
    const q = input.trim();
    input = '';
    messages = [...messages, { role: 'user', content: q }];
    loading = true;

    const msgIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '', sources: [] }];

    try {
      const res = await fetch(`${API_URL}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: 5 }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;
          try {
            const data = JSON.parse(payload);
            if (data.type === 'text') {
              const m = [...messages];
              m[msgIdx] = { ...m[msgIdx], content: m[msgIdx].content + data.content };
              messages = m;
            } else if (data.type === 'sources') {
              const m = [...messages];
              m[msgIdx] = { ...m[msgIdx], sources: data.content };
              messages = m;
            }
          } catch {}
        }
      }
    } catch (e) {
      const m = [...messages];
      m[msgIdx] = { role: 'assistant', content: 'Error: could not reach ingestion worker.', sources: [] };
      messages = m;
    }
    loading = false;
  }

  async function loadDocs() {
    try {
      const res = await fetch(`${API_URL}/documents`);
      documents = await res.json();
      showDocs = !showDocs;
    } catch {
      documents = [];
      showDocs = true;
    }
  }

  async function deleteDoc(name) {
    await fetch(`${API_URL}/documents/${encodeURIComponent(name)}`, { method: 'DELETE' });
    documents = documents.filter(d => d.filename !== name);
  }
</script>

<div class="app">
  <header>
    <h1>🧠 LRAG</h1>
    <span class="subtitle">Local RAG Chat</span>
    <button class="doc-btn" on:click={toggleTheme}>
      {darkMode ? '☀️' : '🌙'}
    </button>
    <button class="doc-btn" on:click={loadDocs}>
      {showDocs ? '✕ Close' : '📄 Docs'}
    </button>
  </header>

  {#if showDocs}
    <div class="doc-panel">
      <h3>Ingested Documents</h3>
      {#if documents.length === 0}
        <p class="empty">No documents ingested yet.</p>
      {:else}
        {#each documents as doc}
          <div class="doc-item">
            <span>{doc.filename} <em>({doc.chunks} chunks)</em></span>
            <button class="del-btn" on:click={() => deleteDoc(doc.filename)}>✕</button>
          </div>
        {/each}
      {/if}
    </div>
  {/if}

  <div class="messages">
    {#each messages as msg}
      <div class="msg {msg.role}">
        <div class="bubble">{@html msg.content.replace(/\n/g, '<br>')}</div>
        {#if msg.sources?.length}
          <details class="sources">
            <summary>Sources ({msg.sources.length})</summary>
            {#each msg.sources as src}
              <div class="source">
                <strong>{src.filename}</strong> (score: {src.score.toFixed(3)})
                <p>{src.excerpt}</p>
              </div>
            {/each}
          </details>
        {/if}
      </div>
    {/each}
    {#if loading}
      <div class="msg assistant">
        <div class="bubble thinking">Thinking...</div>
      </div>
    {/if}
  </div>

  <form class="input-bar" on:submit|preventDefault={send}>
    <input
      type="text"
      bind:value={input}
      placeholder="Ask a question about your documents..."
      disabled={loading}
    />
    <button type="submit" disabled={loading || !input.trim()}>Send</button>
  </form>
</div>

<style>
  :global(*) { margin: 0; padding: 0; box-sizing: border-box; }
  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f13;
    color: #e0e0e0;
    height: 100vh;
    transition: background 0.3s, color 0.3s;
  }
  :global(body.light) {
    background: #f5f5f7;
    color: #1a1a2e;
  }
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 800px;
    margin: 0 auto;
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid #2a2a35;
    background: #1a1a24;
  }
  :global(body.light) header {
    background: #ffffff;
    border-bottom-color: #e0e0e0;
  }
  header h1 { font-size: 20px; }
  .subtitle { color: #888; font-size: 13px; }
  .doc-btn {
    background: #2a2a35;
    border: 1px solid #3a3a48;
    color: #ccc;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }
  .doc-btn:hover { background: #3a3a48; }
  :global(body.light) .doc-btn {
    background: #e8e8ed;
    border-color: #d0d0d8;
    color: #333;
  }
  :global(body.light) .doc-btn:hover { background: #d8d8e0; }
  .doc-panel {
    background: #1a1a24;
    border-bottom: 1px solid #2a2a35;
    padding: 12px 20px;
  }
  :global(body.light) .doc-panel {
    background: #ffffff;
    border-bottom-color: #e0e0e0;
  }
  .doc-panel h3 { font-size: 14px; margin-bottom: 8px; color: #aaa; }
  .empty { color: #666; font-size: 13px; }
  .doc-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    font-size: 13px;
    border-bottom: 1px solid #222;
  }
  .doc-item em { color: #888; font-size: 12px; }
  .del-btn {
    background: none;
    border: none;
    color: #f55;
    cursor: pointer;
    font-size: 14px;
  }
  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .msg { display: flex; flex-direction: column; }
  .msg.user { align-items: flex-end; }
  .bubble {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 12px;
    line-height: 1.5;
    font-size: 14px;
    white-space: pre-wrap;
  }
  .user .bubble {
    background: #3b82f6;
    color: #fff;
    border-bottom-right-radius: 4px;
  }
  .assistant .bubble {
    background: #2a2a35;
    border-bottom-left-radius: 4px;
  }
  :global(body.light) .assistant .bubble {
    background: #e8e8ed;
    color: #1a1a2e;
  }
  .thinking { color: #888; font-style: italic; }
  .sources {
    margin-top: 6px;
    font-size: 12px;
    color: #888;
    max-width: 80%;
  }
  .sources summary { cursor: pointer; color: #5a9cff; }
  .source {
    padding: 6px 0;
    border-bottom: 1px solid #222;
  }
  .source p { margin-top: 4px; color: #aaa; }
  .input-bar {
    display: flex;
    gap: 8px;
    padding: 16px 20px;
    border-top: 1px solid #2a2a35;
    background: #1a1a24;
  }
  :global(body.light) .input-bar {
    background: #ffffff;
    border-top-color: #e0e0e0;
  }
  .input-bar input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid #3a3a48;
    border-radius: 8px;
    background: #0f0f13;
    color: #e0e0e0;
    font-size: 14px;
    outline: none;
  }
  .input-bar input:focus { border-color: #3b82f6; }
  :global(body.light) .input-bar input {
    background: #f5f5f7;
    border-color: #d0d0d8;
    color: #1a1a2e;
  }
  .input-bar button {
    padding: 10px 20px;
    background: #3b82f6;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
  }
  .input-bar button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
