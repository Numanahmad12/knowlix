/**
 * Backend contract — FastAPI backend at ../backend/
 * (see backend README / contract in the parent task).
 *
 *   GET    /api/health            -> { status, version, llm_mode }
 *   POST   /api/upload            multipart, field "file" (PDF, max 20 MB / 500 pages)
 *                                 -> { session_id, filename, page_count, word_count,
 *                                      chunk_count, dense_available,
 *                                      retrieval_mode, summary, sensitive_data }
 *   POST   /api/sample            no body -> same shape as /api/upload
 *   POST   /api/ask               JSON { session_id, question }
 *                                 -> { answer, citations, support: { supported, total },
 *                                      refused, best_score, dense_available,
 *                                      retrieval_label, chunks: [{ page, text }] }
 *   DELETE /api/session/{id}      -> { status: "ok" }
 */

export const API_URL =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export const RELEVANCE_GATE = 0.4;
export const MAX_FILE_SIZE_MB = 20;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
export const MAX_PDF_PAGES = 500;

export class ApiError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(res, fallback) {
  try {
    const data = await res.json();
    return data.detail || data.message || data.error || fallback;
  } catch {
    return fallback;
  }
}

async function handleResponse(res, fallback) {
  if (!res.ok) {
    throw new ApiError(await parseError(res, fallback), res.status);
  }
  return res.json();
}

function fetchWithTimeout(url, options = {}, timeoutMs = 120000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

export async function checkHealth() {
  try {
    const res = await fetchWithTimeout(`${API_URL}/api/health`, {}, 10000);
    if (!res.ok) return { ok: false, data: null };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, data: null };
  }
}

export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  let res;
  try {
    res = await fetchWithTimeout(`${API_URL}/api/upload`, {
      method: "POST",
      body: form,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new ApiError("Upload timed out — the backend took too long to respond.");
    }
    throw new ApiError(
      "Backend unreachable — is the API running at " + API_URL + "?",
      null
    );
  }
  return handleResponse(
    res,
    "Upload rejected — the backend could not analyze that PDF."
  );
}

export async function loadSample() {
  let res;
  try {
    res = await fetchWithTimeout(`${API_URL}/api/sample`, { method: "POST" });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new ApiError("Loading the sample timed out.");
    }
    throw new ApiError(
      "Backend unreachable — is the API running at " + API_URL + "?",
      null
    );
  }
  return handleResponse(res, "Could not load the sample document.");
}

export async function askQuestion(sessionId, question) {
  let res;
  try {
    res = await fetchWithTimeout(`${API_URL}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, question }),
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new ApiError("The question timed out — please try again.");
    }
    throw new ApiError(
      "Backend unreachable — is the API running at " + API_URL + "?",
      null
    );
  }
  return handleResponse(res, "Could not answer that question.");
}

export async function deleteSession(sessionId) {
  // Best-effort: clearing the UI must work even if the backend is gone.
  try {
    const res = await fetchWithTimeout(
      `${API_URL}/api/session/${encodeURIComponent(sessionId)}`,
      { method: "DELETE" },
      10000
    );
    if (!res.ok) return false;
    return true;
  } catch {
    return false;
  }
}

export function retrievalLabel(doc) {
  if (!doc) return "—";
  if (doc.retrieval_mode === "hybrid") return "Hybrid (FAISS)";
  if (doc.retrieval_mode === "keyword") return "Keyword-only";
  return doc.dense_available ? "Hybrid (FAISS)" : "Keyword-only";
}
