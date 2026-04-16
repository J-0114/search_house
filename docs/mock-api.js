/* ── Mock API · GitHub Pages demo mode ─────────────────────────────────────
   Intercepts all fetch() calls to '__MOCK__/*' and serves them from
   localStorage so the app works fully client-side with no backend.
   ──────────────────────────────────────────────────────────────────────── */
(function () {
  /* ── Seed tasks ── */
  var SEED = [
    {id:1,title:"Transformer fault — Almada Norte",description:"Main transformer tripped, ~3000 customers affected. Urgent repair needed.",status:"in_progress",priority:"critical",category:"outage_response",location:"Almada Norte, Almada",asset_id:"TR-9021-STB",user_id:1,created_at:"2026-04-10T08:00:00Z",updated_at:"2026-04-10T09:30:00Z"},
    {id:2,title:"Smart meter inspection — Restelo",description:"Quarterly inspection of 45 smart meters in the Restelo zone.",status:"assigned",priority:"medium",category:"meter_inspection",location:"Restelo, Lisboa",asset_id:"MT-4512-LX",user_id:1,created_at:"2026-04-11T10:00:00Z",updated_at:"2026-04-11T10:00:00Z"},
    {id:3,title:"Solar panel installation — Cascais",description:"Install 12 kW solar array on residential building.",status:"reported",priority:"low",category:"solar_installation",location:"Cascais, Portugal",asset_id:null,user_id:1,created_at:"2026-04-12T14:00:00Z",updated_at:"2026-04-12T14:00:00Z"},
    {id:4,title:"EV charging station fault — Sintra",description:"Charging unit 3 not responding to remote commands.",status:"reported",priority:"high",category:"ev_charging",location:"Sintra, Portugal",asset_id:"EV-003-SNT",user_id:1,created_at:"2026-04-13T09:00:00Z",updated_at:"2026-04-13T09:00:00Z"},
    {id:5,title:"Grid maintenance — Porto Norte",description:"Scheduled annual maintenance of HV lines.",status:"resolved",priority:"medium",category:"grid_maintenance",location:"Porto Norte, Porto",asset_id:"HV-220-PRT",user_id:1,created_at:"2026-04-14T07:00:00Z",updated_at:"2026-04-15T16:00:00Z"},
    {id:6,title:"Safety inspection — Setúbal substation",description:"Annual safety inspection required before summer load peak.",status:"assigned",priority:"high",category:"safety_inspection",location:"Setúbal, Portugal",asset_id:"SUB-STB-01",user_id:1,created_at:"2026-04-15T11:00:00Z",updated_at:"2026-04-15T11:00:00Z"},
  ];

  /* ── localStorage helpers ── */
  function dbLoad() {
    return {
      users:    JSON.parse(localStorage.getItem('_mu') || '[]'),
      tasks:    JSON.parse(localStorage.getItem('_mt') || 'null'),
      comments: JSON.parse(localStorage.getItem('_mc') || '{}'),
      nt: +(localStorage.getItem('_mnt') || 7),
      nu: +(localStorage.getItem('_mnu') || 2),
      nc: +(localStorage.getItem('_mnc') || 1),
    };
  }
  function dbSave(db) {
    localStorage.setItem('_mu',  JSON.stringify(db.users));
    localStorage.setItem('_mt',  JSON.stringify(db.tasks));
    localStorage.setItem('_mc',  JSON.stringify(db.comments));
    localStorage.setItem('_mnt', db.nt);
    localStorage.setItem('_mnu', db.nu);
    localStorage.setItem('_mnc', db.nc);
  }

  /* Seed once on first visit */
  if (!localStorage.getItem('_mt')) {
    var _db = dbLoad(); _db.tasks = SEED; dbSave(_db);
  }

  /* ── Fake JWT (base64 payload only — decoded by existing atob() call) ── */
  function makeJwt(uid, role) {
    var payload = btoa(JSON.stringify({ sub: uid, role: role, exp: Math.floor(Date.now() / 1e3) + 3600 }));
    return 'eyJhbGciOiJub25lIn0.' + payload + '.demo';
  }

  /* ── Response helpers ── */
  function jsonRes(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  function errRes(msg, status) { return jsonRes({ detail: msg }, status || 400); }
  function noContent()         { return new Response(null, { status: 204 }); }

  /* ── Auth helpers ── */
  function uidFromHeaders(h) {
    try {
      var token = ((h || {}).Authorization || '').replace('Bearer ', '');
      return JSON.parse(atob(token.split('.')[1])).sub;
    } catch (e) { return 1; }
  }
  function emailFromHeaders(h, db) {
    var u = db.users.find(function (u) { return u.id === uidFromHeaders(h); });
    return u ? u.email : 'demo@edp.pt';
  }

  /* ── Intercept fetch ── */
  var _origFetch = window.fetch.bind(window);
  window.fetch = async function (url, opts) {
    opts = opts || {};
    var s = String(url);
    if (!s.startsWith('__MOCK__')) return _origFetch(url, opts);

    var path   = s.slice(8);          /* strip '__MOCK__' prefix */
    var method = (opts.method || 'GET').toUpperCase();
    var db     = dbLoad();
    var h      = opts.headers || {};
    var body   = {};
    try { if (opts.body && typeof opts.body === 'string') body = JSON.parse(opts.body); } catch (e) {}

    /* ── Auth ── */
    if (method === 'POST' && path === '/auth/login') {
      var u = db.users.find(function (u) { return u.email === body.email; });
      if (!u) {
        /* auto-create: first user gets admin, rest get user */
        u = { id: db.nu++, email: body.email, role: db.users.length === 0 ? 'admin' : 'user' };
        db.users.push(u);
        dbSave(db);
      }
      return jsonRes({ access_token: makeJwt(u.id, u.role) });
    }

    if (method === 'POST' && path === '/auth/register') {
      if (db.users.find(function (u) { return u.email === body.email; }))
        return errRes('Email already registered', 409);
      if (!body.password || body.password.length < 8)
        return errRes('Password must be at least 8 characters', 422);
      var nu = { id: db.nu++, email: body.email, role: db.users.length === 0 ? 'admin' : 'user' };
      db.users.push(nu);
      dbSave(db);
      return jsonRes(nu, 201);
    }

    if (method === 'POST' && path === '/auth/refresh') {
      var uid2 = uidFromHeaders(h);
      var ru = db.users.find(function (u) { return u.id === uid2; });
      return ru ? jsonRes({ access_token: makeJwt(ru.id, ru.role) }) : jsonRes({}, 401);
    }

    /* ── Tasks list ── */
    if (method === 'GET' && (path === '/tasks' || path.startsWith('/tasks?'))) {
      var qs       = new URLSearchParams(path.includes('?') ? path.split('?')[1] : '');
      var page     = +(qs.get('page')  || 1);
      var lim      = +(qs.get('limit') || 20);
      var q        = (qs.get('q') || '').toLowerCase();
      var tasks    = (db.tasks || []).slice().reverse();
      if (q)                   tasks = tasks.filter(function (t) { return (t.title + ' ' + (t.description || '')).toLowerCase().includes(q); });
      if (qs.get('status'))    tasks = tasks.filter(function (t) { return t.status   === qs.get('status');   });
      if (qs.get('priority'))  tasks = tasks.filter(function (t) { return t.priority === qs.get('priority'); });
      if (qs.get('category'))  tasks = tasks.filter(function (t) { return t.category === qs.get('category'); });
      var total = tasks.length;
      var pages = Math.max(1, Math.ceil(total / lim));
      return jsonRes({ tasks: tasks.slice((page - 1) * lim, page * lim), total: total, page: page, pages: pages });
    }

    /* ── Create task ── */
    if (method === 'POST' && path === '/tasks') {
      if (!body.title || body.title.length < 3) return errRes('Title must be at least 3 characters', 422);
      var newTask = Object.assign({}, body, {
        id: db.nt++,
        user_id: uidFromHeaders(h),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      });
      db.tasks.push(newTask);
      dbSave(db);
      return jsonRes(newTask, 201);
    }

    /* ── Single task PATCH / DELETE ── */
    var tm = path.match(/^\/tasks\/(\d+)$/);
    if (tm) {
      var taskId = +tm[1];
      if (method === 'PATCH') {
        var idx = db.tasks.findIndex(function (t) { return t.id === taskId; });
        if (idx === -1) return errRes('Not found', 404);
        db.tasks[idx] = Object.assign({}, db.tasks[idx], body, { id: taskId, updated_at: new Date().toISOString() });
        dbSave(db);
        return jsonRes(db.tasks[idx]);
      }
      if (method === 'DELETE') {
        db.tasks = db.tasks.filter(function (t) { return t.id !== taskId; });
        delete db.comments[taskId];
        dbSave(db);
        return noContent();
      }
    }

    /* ── Comments ── */
    var cm = path.match(/^\/tasks\/(\d+)\/comments$/);
    if (cm) {
      var cTaskId = +cm[1];
      if (method === 'GET') return jsonRes(db.comments[cTaskId] || []);
      if (method === 'POST') {
        var comment = {
          id: db.nc++,
          task_id: cTaskId,
          author: emailFromHeaders(h, db),
          body: body.body,
          created_at: new Date().toISOString()
        };
        if (!db.comments[cTaskId]) db.comments[cTaskId] = [];
        db.comments[cTaskId].push(comment);
        dbSave(db);
        return jsonRes(comment, 201);
      }
    }

    var dcm = path.match(/^\/tasks\/(\d+)\/comments\/(\d+)$/);
    if (dcm && method === 'DELETE') {
      var dct = +dcm[1], dcc = +dcm[2];
      if (db.comments[dct]) db.comments[dct] = db.comments[dct].filter(function (c) { return c.id !== dcc; });
      dbSave(db);
      return noContent();
    }

    /* ── Attachments (stubbed — binary storage not supported in demo) ── */
    if (path.match(/^\/tasks\/\d+\/attachments$/) && method === 'GET')    return jsonRes([]);
    if (path.match(/^\/tasks\/\d+\/attachments$/) && method === 'POST')   return errRes('File upload not supported in demo mode', 501);
    if (path.match(/^\/tasks\/\d+\/attachments\/\d+$/) && method === 'DELETE') return noContent();
    if (path.match(/^\/tasks\/\d+\/attachments\/\d+$/) && method === 'GET')    return errRes('File download not supported in demo mode', 501);

    /* ── Audit ── */
    if (path.match(/^\/tasks\/\d+\/audit$/) && method === 'GET') return jsonRes([]);

    /* ── Admin ── */
    if (method === 'GET' && path === '/admin/users') return jsonRes(db.users);
    var rm = path.match(/^\/admin\/users\/(\d+)\/role$/);
    if (rm && method === 'PATCH') {
      var ru2 = db.users.find(function (u) { return u.id === +rm[1]; });
      if (!ru2) return errRes('Not found', 404);
      ru2.role = body.role;
      dbSave(db);
      return jsonRes(ru2);
    }

    return errRes('Not found', 404);
  };

  window._mockMode = true;
})();
