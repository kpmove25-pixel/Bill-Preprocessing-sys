/* 前端主逻辑 */
const App = {
  state: {
    currentTaskId: null,
    invoices: [],
    tasks: [],
    files: [],
  },

  COLS: [
    { key: "invoice_code", label: "发票代码", edit: true },
    { key: "invoice_no", label: "发票号码", edit: true },
    { key: "invoice_type", label: "发票类型", edit: true },
    { key: "buyer_name", label: "购买方名称", edit: true },
    { key: "buyer_tax_no", label: "购买方税号", edit: true },
    { key: "amount", label: "金额", edit: true },
    { key: "amount_excluding_tax", label: "不含税金额", edit: true },
    { key: "tax_amount", label: "税额", edit: true },
    { key: "tax_rate", label: "税率", edit: true },
    { key: "invoice_date", label: "开票日期", edit: true },
    { key: "seller_name", label: "销售方名称", edit: true },
    { key: "seller_tax_no", label: "销售方税号", edit: true },
    { key: "check_code", label: "校验码", edit: true },
    { key: "drawer", label: "开票人", edit: true },
    { key: "original_filename", label: "原文件名" },
    { key: "status", label: "状态", edit: true },
    { key: "remark", label: "备注", edit: true },
  ],

  toast(msg, type) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast " + (type || "success");
    t.style.display = "block";
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (t.style.display = "none"), 2500);
  },

  async init() {
    try {
      await api.listTasks();
      this.showApp();
    } catch (e) {
      this.showLogin();
    }
  },

  showLogin() {
    document.getElementById("login-page").style.display = "flex";
    document.getElementById("app").style.display = "none";
  },
  showApp() {
    document.getElementById("login-page").style.display = "none";
    document.getElementById("app").style.display = "block";
    this.loadTasks();
  },

  async login() {
    const u = document.getElementById("login-user").value;
    const p = document.getElementById("login-pass").value;
    try {
      const r = await api.login(u, p);
      api.setToken(r.token);
      document.getElementById("login-error").textContent = "";
      this.showApp();
    } catch (e) {
      document.getElementById("login-error").textContent = e.message;
    }
  },

  logout() {
    api.clearToken();
    this.showLogin();
  },

  nav(page) {
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    document.getElementById("page-" + page).classList.add("active");
    document.querySelectorAll(".topbar nav a").forEach((a) => a.classList.remove("active"));
    document.querySelector('.topbar nav a[data-page="' + page + '"]').classList.add("active");
    if (page === "tasks") this.loadTasks();
    if (page === "invoices") this.loadInvoices();
    if (page === "duplicates") this.loadDuplicates();
  },

  setupUpload() {
    const dz = document.getElementById("dropzone");
    const input = document.getElementById("file-input");
    dz.onclick = () => input.click();
    input.onchange = () => this.addFiles(input.files);
    dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("dragover"); };
    dz.ondragleave = () => dz.classList.remove("dragover");
    dz.ondrop = (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
      this.addFiles(e.dataTransfer.files);
    };
  },
  addFiles(fileList) {
    for (const f of fileList) {
      if (!this.state.files.some((x) => x.name === f.name && x.size === f.size)) {
        this.state.files.push(f);
      }
    }
    this.renderFileList();
  },
  renderFileList() {
    const box = document.getElementById("file-list");
    const btn = document.getElementById("btn-upload");
    btn.disabled = this.state.files.length === 0;
    box.innerHTML = this.state.files
      .map(
        (f, i) =>
          `<div class="fitem"><span>${f.name} (${this.fmtSize(f.size)})</span>
           <a href="#" onclick="App.removeFile(${i});return false;">移除</a></div>`
      )
      .join("");
  },
  removeFile(i) {
    this.state.files.splice(i, 1);
    this.renderFileList();
  },
  fmtSize(b) {
    if (b < 1024) return b + " B";
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + " KB";
    return (b / 1024 / 1024).toFixed(1) + " MB";
  },
  async doUpload() {
    const fd = new FormData();
    this.state.files.forEach((f) => fd.append("files", f));
    try {
      const r = await api.upload(fd);
      this.state.files = [];
      this.renderFileList();
      this.toast("已提交任务 " + r.task_id + "，正在后台处理...");
      this.state.currentTaskId = r.task_id;
      this.nav("tasks");
    } catch (e) {
      this.toast(e.message, "error");
    }
  },

  // ---- 任务列表 ----
  async loadTasks() {
    try {
      const tasks = await api.listTasks();
      this.state.tasks = tasks;
      this.renderTasks(tasks);
    } catch (e) {
      this.toast(e.message, "error");
    }
  },
  renderTasks(tasks) {
    const tb = document.getElementById("task-tbody");
    if (!tasks.length) {
      tb.innerHTML = '<tr><td colspan="9" class="empty">暂无任务</td></tr>';
      return;
    }
    const statusMap = { done: "完成", processing: "处理中", pending: "排队中", failed: "失败", cancelled: "已取消" };
    tb.innerHTML = tasks
      .map((t) => {
        const pct = t.progress != null ? t.progress : 0;
        return `<tr>
          <td>${t.task_id}</td>
          <td><span class="badge ${t.status}">${statusMap[t.status] || t.status}</span></td>
          <td style="min-width:120px"><div class="progress"><div class="bar" style="width:${pct}%"></div></div></td>
          <td>${t.total_files}</td>
          <td>${t.success_count}</td>
          <td>${t.failed_count}</td>
          <td>${t.duplicate_count}</td>
          <td>${this.fmtTime(t.created_at)}</td>
          <td>
            <button class="btn small" onclick="App.openTask('${t.task_id}','invoices')">识别结果</button>
            <button class="btn small" onclick="App.openTask('${t.task_id}','duplicates')">重复</button>
            <button class="btn small success" onclick="App.openTask('${t.task_id}','download')">下载</button>
            <button class="btn small gray" onclick="App.retryTask('${t.task_id}')">重试失败</button>
            ${t.status === "pending" || t.status === "processing" ? `<button class="btn small warn" onclick="App.cancelTask('${t.task_id}')">取消</button>` : ""}
            <button class="btn small danger" onclick="App.delTask('${t.task_id}')">删除</button>
          </td>
        </tr>`;
      })
      .join("");
  },
  openTask(id, page) {
    this.state.currentTaskId = id;
    this.nav(page);
  },
  fmtTime(s) {
    if (!s) return "";
    const d = new Date(s.endsWith("Z") ? s : s + "Z");
    return d.toLocaleString("zh-CN");
  },
  async retryTask(id) {
    try {
      const r = await api.retryFailed(id);
      this.toast(r.detail);
      this.loadTasks();
    } catch (e) { this.toast(e.message, "error"); }
  },
  async delTask(id) {
    if (!confirm("确认删除任务 " + id + " 及其所有数据？")) return;
    try {
      await api.deleteTask(id);
      this.toast("已删除");
      this.loadTasks();
    } catch (e) { this.toast(e.message, "error"); }
  },
  async cancelTask(id) {
    try {
      await api.cancelTask(id);
      this.toast("已请求取消");
      this.loadTasks();
    } catch (e) { this.toast(e.message, "error"); }
  },

  // ---- 识别结果 ----
  async loadInvoices() {
    const id = this.state.currentTaskId;
    if (!id) { this.toast("请先从任务列表选择任务", "error"); return; }
    const status = document.getElementById("filter-status") ? document.getElementById("filter-status").value : "";
    const buyer = document.getElementById("filter-buyer") ? document.getElementById("filter-buyer").value : "";
    const no = document.getElementById("filter-no") ? document.getElementById("filter-no").value : "";
    try {
      const invs = await api.listInvoices(id, { status, buyer_name: buyer, invoice_no: no });
      this.state.invoices = invs;
      this.renderInvoices(invs);
    } catch (e) { this.toast(e.message, "error"); }
  },
  renderInvoices(invs) {
    const head = document.getElementById("invoice-head");
    const tb = document.getElementById("invoice-tbody");
    head.innerHTML = "<th class=\"th-seq\">序号</th><th class=\"th-img\">图片</th>" +
      this.COLS.map((c) => `<th>${c.label}</th>`).join("") + "<th>操作</th>";
    if (!invs.length) {
      tb.innerHTML = '<tr><td colspan="' + (this.COLS.length + 3) + '" class="empty">暂无识别结果</td></tr>';
      return;
    }
    const numKeys = ["invoice_code", "invoice_no", "buyer_tax_no", "seller_tax_no", "amount", "amount_excluding_tax", "tax_amount", "tax_rate"];
    tb.innerHTML = invs.map((inv, i) => {
      const cells = this.COLS.map((c) => {
        const val = inv[c.key] == null ? "" : inv[c.key];
        const numCls = numKeys.includes(c.key) ? " num" : "";
        if (c.edit) {
          const hl = inv.need_review || inv.status === "needs_review" ? "highlight" : "";
          if (c.key === "status") {
            const statusMap = { pending: "待确认", confirmed: "已确认", needs_review: "待人工处理", void: "作废" };
            const opts = Object.keys(statusMap)
              .map((s) => `<option value="${s}" ${s === val ? "selected" : ""}>${statusMap[s]}</option>`).join("");
            return `<td class="cell-status"><select class="edit-input ${hl}" data-id="${inv.id}" data-field="${c.key}">${opts}</select></td>`;
          }
          return `<td class="${numCls.trim()}"><input class="edit-input ${hl}" data-id="${inv.id}" data-field="${c.key}" value="${this.escape(val)}" /></td>`;
        }
        return `<td class="${numCls.trim()}">${this.escape(val)}</td>`;
      }).join("");
      const dupTag = inv.is_duplicate
        ? ' <span class="badge duplicate" title="重复票据（任务内或历史）">重复</span>'
        : "";
      return `<tr class="${inv.is_duplicate ? "dup-row" : ""}"><td class="cell-seq">${i + 1}${dupTag}</td>
        <td class="cell-img"><a href="${api.imageUrl(inv.id)}" target="_blank" title="查看原图"><img src="${api.imageUrl(inv.id)}" loading="lazy" /></a></td>
        ${cells}
        <td><button class="btn small" onclick="App.saveOne(${inv.id})">保存</button></td></tr>`;
    }).join("");
  },
  escape(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  },
  collectChanges(invId) {
    const inputs = document.querySelectorAll(`.edit-input[data-id="${invId}"]`);
    const body = {};
    inputs.forEach((el) => {
      const field = el.getAttribute("data-field");
      const newVal = el.value;
      const inv = this.state.invoices.find((x) => x.id === Number(invId));
      if (inv && String(inv[field] || "") !== newVal) body[field] = newVal;
    });
    return body;
  },
  async saveOne(invId) {
    const body = this.collectChanges(invId);
    if (!Object.keys(body).length) { this.toast("无修改"); return; }
    try {
      await api.updateInvoice(invId, body);
      this.toast("已保存");
      this.loadInvoices();
    } catch (e) { this.toast(e.message, "error"); }
  },
  async saveCurrentInvoice() {
    const ids = new Set();
    document.querySelectorAll(".edit-input").forEach((el) => ids.add(el.getAttribute("data-id")));
    for (const invId of ids) {
      const body = this.collectChanges(invId);
      if (Object.keys(body).length) {
        try { await api.updateInvoice(Number(invId), body); } catch (e) {}
      }
    }
    this.toast("已保存所有修改");
    this.loadInvoices();
  },
  async reExport() {
    await this.saveCurrentInvoice();
    const id = this.state.currentTaskId;
    try {
      const r = await api.exportTask(id);
      this.toast(r.detail);
    } catch (e) { this.toast(e.message, "error"); }
  },

  // ---- 重复 ----
  async loadDuplicates() {
    const id = this.state.currentTaskId;
    if (!id) { this.toast("请先从任务列表选择任务", "error"); return; }
    try {
      const dups = await api.listDuplicates(id);
      const tb = document.getElementById("dup-tbody");
      if (!dups.length) {
        tb.innerHTML = '<tr><td colspan="8" class="empty">无重复记录</td></tr>';
        return;
      }
      tb.innerHTML = dups.map((d) => `<tr><td>${d.invoice_no}</td><td>${d.invoice_code}</td><td>${d.invoice_type}</td>
        <td>${d.buyer_name}</td><td>${d.buyer_tax_no}</td><td>${d.kept_file}</td>
        <td>${d.skipped_file}</td><td>${d.processed_at}</td></tr>`).join("");
    } catch (e) { this.toast(e.message, "error"); }
  },
  downloadDuplicates() {
    const id = this.state.currentTaskId;
    if (id) window.location.href = api.downloadUrl(id, "duplicates");
  },

  // ---- 下载 ----
  downloadAll() {
    const id = this.state.currentTaskId;
    if (id) window.location.href = api.downloadUrl(id);
  },

  // ---- 票据查重 ----
  ledgerKeydown(e) {
    if (e.key === "Enter") { e.preventDefault(); this.checkLedger(); }
  },

  async checkLedger() {
    const no = document.getElementById("ledger-no").value.trim();
    const code = document.getElementById("ledger-code").value.trim();
    if (!no) { this.toast("请输入发票号码", "error"); return; }
    try {
      const r = await api.checkLedger(no, code);
      const box = document.getElementById("ledger-result");
      if (!r.found) {
        box.innerHTML = '<div class="empty">该票据未被使用过（未查询到历史处理记录）</div>';
        return;
      }
      const e = r.entry;
      const rows = [
        ["发票号码", e.invoice_no],
        ["发票代码", e.invoice_code],
        ["发票类型", e.invoice_type],
        ["购买方", e.buyer_name],
        ["销售方", e.seller_name],
        ["金额", e.amount],
        ["使用时间", e.first_seen_at],
      ];
      box.innerHTML =
        '<div class="ledger-hit">✅ 该票据已使用</div>' +
        '<div class="ledger-card">' +
        rows.map((kv) => '<div class="ledger-row"><span class="ledger-label">' + this.escape(kv[0]) + '</span><span class="ledger-value">' + this.escape(kv[1] || "—") + '</span></div>').join("") +
        '</div>';
    } catch (err) { this.toast(err.message, "error"); }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  App.setupUpload();
  App.init();
  setInterval(() => {
    if (document.getElementById("page-tasks").classList.contains("active")) {
      App.loadTasks();
    }
  }, 3000);
});
