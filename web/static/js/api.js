/* API 封装：统一 token 注入与错误处理 */
(function () {
  const TOKEN_KEY = "invoice_token";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }
  function setToken(t) {
    localStorage.setItem(TOKEN_KEY, t);
  }
  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  async function request(method, url, body) {
    const headers = {};
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    const opts = { method, headers };
    if (body !== undefined) {
      if (body instanceof FormData) {
        opts.body = body;
      } else {
        headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
      }
    }
    const res = await fetch(url, opts);
    if (res.status === 401) {
      clearToken();
      throw new Error("未登录或会话已过期");
    }
    if (!res.ok) {
      let msg = "请求失败 (" + res.status + ")";
      try {
        const j = await res.json();
        if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch (e) {}
      throw new Error(msg);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.indexOf("application/json") !== -1) return res.json();
    return res;
  }

  const api = {
    getToken,
    setToken,
    clearToken,
    request,
    login: (u, p) => request("POST", "/api/auth/login", { username: u, password: p }),
    upload: (formData) => request("POST", "/api/tasks/upload", formData),
    listTasks: () => request("GET", "/api/tasks"),
    getTask: (id) => request("GET", "/api/tasks/" + id),
    listInvoices: (id, params) => {
      const q = new URLSearchParams();
      if (params) for (const k in params) if (params[k]) q.set(k, params[k]);
      return request("GET", "/api/tasks/" + id + "/invoices?" + q.toString());
    },
    updateInvoice: (id, body) => request("PUT", "/api/invoices/" + id, body),
    exportTask: (id) => request("POST", "/api/tasks/" + id + "/export"),
    listDuplicates: (id) => request("GET", "/api/tasks/" + id + "/duplicates"),
    checkLedger: (no, code) => request("POST", "/api/ledger/check", { invoice_no: no, invoice_code: code || "" }),
    retryFailed: (id) => request("POST", "/api/tasks/" + id + "/retry-failed"),
    cancelTask: (id) => request("POST", "/api/tasks/" + id + "/cancel"),
    deleteTask: (id) => request("DELETE", "/api/tasks/" + id),
    downloadUrl: (id, type) => {
      const token = getToken();
      let url = "/api/tasks/" + id + "/download";
      if (type === "duplicates") url += "/duplicates";
      return url + (token ? (url.indexOf("?") === -1 ? "?token=" : "&token=") + token : "");
    },
    imageUrl: (id) => {
      const token = getToken();
      const url = "/api/invoices/" + id + "/image";
      return url + (token ? (url.indexOf("?") === -1 ? "?token=" : "&token=") + token : "");
    },
  };

  window.api = api;
})();
