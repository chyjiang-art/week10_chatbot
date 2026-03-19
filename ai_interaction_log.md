### Task: Task 1A: Page Setup and API Connection
**Prompt:** Build a basic Streamlit chat app shell with Hugging Face API access, including page setup, hardcoded test message flow, and robust error handling for token and request failures.
**AI Suggestion:** Generated a minimal working app with page config/title, HF token loading from `st.secrets`, request call to Hugging Face chat completions, and explicit checks for missing token, timeout, network errors, invalid token, rate limit, non-200 responses, and invalid payload format.
**My Modifications & Reflections:** I fixed syntax issues from the generated draft, kept the flow simple, and made sure each error path stops safely without crashing. I verified the single-message path worked end-to-end before moving on.

### Task: Task 1B: Multi-Turn Conversation UI
**Prompt:** Replace hardcoded messaging with a real multi-turn chat UI using Streamlit chat components and session state history.
**AI Suggestion:** Suggested switching to `st.chat_input`, rendering messages with `st.chat_message`, storing user/assistant turns in `st.session_state`, and sending full history to the model each time.
**My Modifications & Reflections:** I implemented the session-based history flow and kept logic beginner-readable. I checked message order and made sure assistant replies append to history after each call so context is preserved across turns.

### Task: Task 1C: Chat Management
**Prompt:** Add sidebar chat management with multiple sessions, including new chat, switching between chats, deleting chats, and active-chat visual feedback.
**AI Suggestion:** Added `st.session_state` chat list, sidebar buttons for chat selection, a new chat button, delete action, and active chat indicator styling.
**My Modifications & Reflections:** I kept the existing multi-turn structure and changed only UI details to avoid confusion (simple labels, readable layout, no symbols). I tuned sidebar behavior so switching and deleting do not overwrite other chats.

### Task 1D: Chat Persistence
**Prompt:** Persist chats to disk in JSON files under `chats/`, load existing chats on startup, and keep files in sync for create/save/delete actions.
**AI Suggestion:** Implemented per-chat JSON files storing id, title, timestamp, and full messages; load/save flow on startup and updates; delete operation removes file too.
**My Modifications & Reflections:** I kept the in-memory session state and file persistence behavior aligned. I also improved timestamp display for compactness in the sidebar while still saving full timestamps in storage.

### Task: Task 2: Response Streaming
**Prompt:** Enable streamed assistant responses so text appears incrementally in the chat UI while handling API SSE chunks and preserving state.
**AI Suggestion:** Added `stream=True` request mode, SSE parsing loop, incremental UI updates in a `st.empty()` message box, and final response normalization once streaming ends.
**My Modifications & Reflections:** I fixed draft handling bugs for switching chats mid-stream by keeping draft text in session state and periodic saves, so partial responses are not lost if the user changes chat during generation.

### Task: Task 3: User Memory
**Prompt:** Add persistent user memory extraction, storage, loading, display, reset, and memory injection into future model requests.
**AI Suggestion:** Added a second lightweight extraction call after each assistant response, memory merge logic, JSON file persistence, sidebar expander display, reset control, and inclusion of memory context in future requests.
**My Modifications & Reflections:** I simplified memory schema to explicit keys only, removed speculative/default values, made extraction strict to latest user message, and changed sidebar display to readable labeled lines instead of raw JSON. I also fixed issues where inferred facts were appearing and ensured memory persists through `memory.json`.
